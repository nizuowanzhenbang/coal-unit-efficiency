"""Freeze calculation inputs independently of mutable unit/configuration data."""

from hashlib import sha256
import json


def attach_input_evidence(result, optimizer, unit, snapshot, standard_coal_price: float) -> None:
    inputs = {
        **result.evaluation['current_features'],
        'capacity_mw': unit.capacity_mw,
        'coal_lhv': snapshot.coal_lhv,
        'standard_coal_price': standard_coal_price,
        'o2_sensitivity': optimizer.o2_sensitivity,
        'fly_ash_target': optimizer.fly_ash_target,
    }
    canonical = json.dumps(inputs, sort_keys=True, separators=(',', ':'), allow_nan=False)
    result.evaluation.update(input_snapshot=inputs, input_sha256=sha256(canonical.encode()).hexdigest())
