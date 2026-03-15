# Trade Intel Reason Codes

Reason codes are centralized in `trade_intel/reason_codes.py`:
- Sizing codes (`SIZE_*`)
- Entry codes (`ENTRY_*`)
- Exit codes (`EXIT_*`)
- Attribution codes (`ATTR_*`)
- Edge-decay codes (`EDGE_*`)

The runtime uses these codes for every block/downsize/exit/attribution classification.
