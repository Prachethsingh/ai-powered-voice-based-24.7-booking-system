/**
 * ari_handler.js — Asterisk ARI integration for ai powered voice based 24.7 booking system
 *
 * Handles:
 *  - Incoming call events (StasisStart)
 *  - Audio streaming to Python STT
 *  - TTS playback
 *  - Call hangup cleanup
 *
 * Security:
 *  - IP whitelisted ARI connection
 *  - Rate limiting per call
 *  - Input validation on channel IDs
 */
import ari from "ari-client";
import axios from "axios";
import { validateCallId, sanitizeString } from "./auth.js";

const PYTHON_API = process.env.PYTHON_API_URL || "http://127.0.0.1:8001";
const MAX_CALL_DURATION_MS = 120_000; // 2 minutes max per call

export class AsteriskHandler {
  constructor({ host, port, user, password, onCallResult }) {
    this.host = host;
    this.port = port;
    this.user = user;
    this.password = password;
    this.onCallResult = onCallResult; // Callback: send result to WebSocket
    this.client = null;
    this.activeCalls = new Map(); // callId → {timer, audioChunks}
  }

  async connect() {
    const url = `http://${this.host}:${this.port}/`;
    this.client = await ari.connect(url, this.user, this.password);
    console.log("[ARI] ✅ Connected to Asterisk");

    // Register event handlers
    this.client.on("StasisStart", this._onCallStart.bind(this));
    this.client.on("ChannelHangupRequest", this._onHangup.bind(this));
    this.client.on("ChannelDtmfReceived", this._onDTMF.bind(this));

    this.client.start(["booking-system"]);
    console.log("[ARI] Listening for calls on app: booking-system");
  }

  // ── Call Start ─────────────────────────────────────────────────────────

  async _onCallStart(event, channel) {
    const callId = channel.id;
    if (!validateCallId(callId)) {
      console.warn(`[ARI] Invalid call ID rejected: ${callId}`);
      await channel.hangup().catch(() => {});
      return;
    }

    const callerNum = channel.caller?.number || "unknown";
    console.log(`[ARI] 📞 Incoming call | ID: ${callId} | From: ${callerNum}`);

    // Answer
    await channel.answer();

    // Track call
    const callTimer = setTimeout(async () => {
      console.warn(`[ARI] [${callId}] Max duration reached, hanging up`);
      await this._hangupCall(callId, channel);
    }, MAX_CALL_DURATION_MS);

    this.activeCalls.set(callId, {
      timer: callTimer,
      channel,
      callerNum,
      audioChunks: [],
      startTime: Date.now(),
    });

    // Play greeting
    await this._play(channel, "sound:hello-world").catch(() =>
      console.warn(`[ARI] [${callId}] Greeting sound not found (ok to ignore)`)
    );

    // Start recording for STT
    await this._startRecording(callId, channel);
  }

  // ── Recording → STT ────────────────────────────────────────────────────

  async _startRecording(callId, channel) {
    /**
     * Record caller audio, send to Python STT/AI pipeline.
     *
     * Strategy: Record 5-second clips, send to /process-audio, play response.
     * This creates a simple turn-based conversation.
     */
    const call = this.activeCalls.get(callId);
    if (!call) return;

    const recordingName = `vb_${callId}_${Date.now()}`;

    try {
      // Start recording (silence-terminated, max 10s)
      const recording = await channel.record({
        name: recordingName,
        format: "wav",
        maxDurationSeconds: 10,
        maxSilenceSeconds: 2,   // Stop after 2s silence
        ifExists: "overwrite",
        beep: false,
      });

      // Wait for recording to finish
      recording.once("RecordingFinished", async (event) => {
        console.log(`[ARI] [${callId}] Recording done: ${recordingName}.wav`);
        await this._processRecording(callId, channel, recordingName);
      });

      recording.once("RecordingFailed", (event) => {
        console.error(`[ARI] [${callId}] Recording failed:`, event);
      });

    } catch (err) {
      console.error(`[ARI] [${callId}] Record error:`, err.message);
    }
  }

  async _processRecording(callId, channel, recordingName) {
    /**
     * Send recorded audio to Python AI pipeline.
     * Play TTS response back to caller.
     */
    const call = this.activeCalls.get(callId);
    if (!call) return;

    try {
      // Read the recording file (Asterisk saves to /var/spool/asterisk/recording/)
      const recordingPath = `/var/spool/asterisk/recording/${recordingName}.wav`;

      // Send to Python pipeline
      const response = await axios.post(`${PYTHON_API}/process-audio`, {
        call_id: callId,
        audio_path: recordingPath,  // Python reads file directly
        sample_rate: 8000,          // Asterisk default
      }, { timeout: 15_000 });

      const result = response.data;
      console.log(`[ARI] [${callId}] AI result: ${JSON.stringify(result)}`);

      // Build TTS response
      const ttsText = this._buildTTSText(result);

      // Play response (use Asterisk's built-in TTS or pre-recorded sounds)
      await this._playTTS(callId, channel, ttsText, result.status);

      // Notify WebSocket dashboard
      if (this.onCallResult) {
        this.onCallResult({ callId, ...result });
      }

      // If order success or terminal state, hang up
      if (["success", "rate_limited"].includes(result.status)) {
        setTimeout(() => this._hangupCall(callId, channel), 3000);
      } else {
        // Try again (ask user to repeat)
        setTimeout(() => this._startRecording(callId, channel), 1000);
      }

    } catch (err) {
      console.error(`[ARI] [${callId}] Processing error:`, err.message);
      await this._play(channel, "sound:sorry").catch(() => {});
      await this._hangupCall(callId, channel);
    }
  }

  _buildTTSText(result) {
    const statusMessages = {
      success:      `Order confirmed. Items: ${(result.items || []).join(", ")}.`,
      no_phone:     "Please say your 10-digit phone number clearly.",
      no_items:     "Please tell us what items you would like to order.",
      duplicate:    "You already have a recent order. We have it on record.",
      rate_limited: "Too many orders today. Please try again tomorrow.",
      error:        "Sorry, something went wrong. Please call again.",
    };
    return statusMessages[result.status] || statusMessages.error;
  }

  // ── Audio Playback ─────────────────────────────────────────────────────

  async _play(channel, sound) {
    return channel.play({ media: sound });
  }

  async _playTTS(callId, channel, text, status) {
    /**
     * TTS Playback Strategy:
     * 1. Try pre-recorded audio files (fastest, best quality)
     * 2. Fall back to Asterisk Festival TTS (if installed)
     * 3. Fall back to generic sounds
     */
    const soundMap = {
      success:      "sound:order-confirmed",
      no_phone:     "sound:please-say-phone",
      no_items:     "sound:please-say-items",
      duplicate:    "sound:order-exists",
      rate_limited: "sound:too-many-orders",
      error:        "sound:sorry",
    };

    // Try pre-recorded sound
    const sound = soundMap[status] || "sound:sorry";
    try {
      await this._play(channel, sound);
    } catch {
      // Fall back to Asterisk Festival TTS
      try {
        await this._play(channel, `say:${text}`);
      } catch {
        await this._play(channel, "sound:goodbye").catch(() => {});
      }
    }
  }

  // ── DTMF (Touch-tone fallback) ─────────────────────────────────────────

  async _onDTMF(event, channel) {
    const digit = event.digit;
    const callId = channel.id;
    console.log(`[ARI] [${callId}] DTMF: ${digit}`);
    // Future: allow phone number entry via DTMF keypad
  }

  // ── Hangup ─────────────────────────────────────────────────────────────

  async _onHangup(event, channel) {
    const callId = channel.id;
    await this._hangupCall(callId, channel);
  }

  async _hangupCall(callId, channel) {
    const call = this.activeCalls.get(callId);
    if (call) {
      clearTimeout(call.timer);
      this.activeCalls.delete(callId);
    }
    const duration = call ? Math.round((Date.now() - call.startTime) / 1000) : 0;
    console.log(`[ARI] [${callId}] Call ended (${duration}s)`);

    try {
      await channel.hangup();
    } catch {
      // Already hung up, ignore
    }
  }

  getActiveCallCount() {
    return this.activeCalls.size;
  }
}
