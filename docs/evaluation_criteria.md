# Evaluation Criteria Mapping

| Criteria | Weight | Where it's addressed |
|---|---|---|
| Problem Understanding | 15% | `docs/solution_architecture.md` Section 1, `docs/workflow_documentation.md` Phase 1 |
| Accuracy of Order Processing | 25% | `docs/accuracy_approach.md` (ensemble: chain-of-thought + self-consistency + regex cross-check), `backend/python/advanced_pipeline.py`, `backend/python/order_validator.py` |
| System Design & Architecture | 20% | `docs/solution_architecture.md`, 7-phase code mapping in `docs/workflow_documentation.md` |
| Resource Optimization | 20% | CPU-only everywhere (n_gpu_layers=0), ~275MB total model footprint, single-VM deployment, `docs/deployment_approach.md` |
| Dashboard & User Experience | 10% | `frontend/` — live calls, bookings table, metrics charts, security panel, WebSocket real-time updates |
| Documentation & Presentation | 10% | This `docs/` folder + `README.md` + `docs/demo_presentation.md` |

### Deliverables checklist

- Solution Architecture: `docs/solution_architecture.md`
- Working Prototype: full `backend/`, `frontend/`, `asterisk/` source tree, runnable via `scripts/start_all.sh` or Docker Compose
- Dashboard: `frontend/` React app with live WebSocket updates
- Workflow Documentation: `docs/workflow_documentation.md` (all 7 phases)
- Demo Presentation: `docs/demo_presentation.md` (~6-minute script with Q&A prep)
- Deployment Approach: `docs/deployment_approach.md`
- Concurrency/Scalability: `docs/concurrency_and_scalability.md` (10-20 simultaneous calls)
- Accuracy Methodology: `docs/accuracy_approach.md`
- Test Suite: `tests/test_security.py`, `tests/test_pipeline.py`
- Offline Test Tool: `call_simulator.py` (no Asterisk/phone required to validate the pipeline)
