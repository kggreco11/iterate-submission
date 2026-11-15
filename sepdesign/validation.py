"""Independent design eligibility checks. Numerical tolerances are provisional.

Convergence plus these checks is not independent energy-balance validation.
"""
from sepdesign.column_rules import optional_settings_errors
import math
import numpy as np


def validate_result(design, result, econ, bounds, max_columns, atol=1e-5, rtol=1e-6):
    errors = []
    residuals = {}
    n = econ.n

    def vector(value, label):
        try:
            a = np.asarray(value, dtype=float)
            if a.shape != (n,) or not np.all(np.isfinite(a)) or np.any(a < 0):
                raise ValueError()
            return a
        except (TypeError, ValueError):
            errors.append(label + ': invalid component vector')
            return None

    def number(value, label, positive=False, nonnegative=False):
        try:
            v = float(value)
            if not math.isfinite(v) or (positive and v <= 0) or (nonnegative and v < 0):
                raise ValueError()
            return v
        except (TypeError, ValueError):
            errors.append(label + ': invalid scalar')
            return None

    def close(a, b, label):
        if a is not None and b is not None:
            residuals[label] = float(np.max(np.abs(a-b)))
            if not np.allclose(a, b, atol=atol, rtol=rtol):
                errors.append(label + ': balance/continuity mismatch')

    nodes = result.get('nodes', {})
    expected = {''}
    for path, spec in design.items():
        if not isinstance(path, str) or set(path) - {'T', 'B', 'S'} or (path and path[:-1] not in design):
            errors.append(f'{path}: invalid topology')
        elif path.endswith('S') and (len(design[path[:-1]]) < 5 or design[path[:-1]][4] is None):
            errors.append(f'{path}: column below a side draw that does not exist')
        has_side = len(spec) > 4 and spec[4] is not None
        expected.update([path, path+'T', path+'B'] + ([path+'S'] if has_side else []))
        if len(spec) not in (4, 5, 6):
            errors.append(f'{path}: invalid settings')
            continue
        errors.extend(f'{path}: {error}' for error in optional_settings_errors(spec, econ.task, bounds))
        for key, value in zip(('n_stages','reflux_ratio','reboil_ratio','pressure_drop_fraction'), spec[:4]):
            val = number(value, f'{path}/{key}')
            if val is not None and (not bounds[key][0] <= val <= bounds[key][1] or (key=='n_stages' and val != int(val))):
                errors.append(f'{path}/{key}: outside bounds')
    if len(design) > max_columns:
        errors.append('column cap exceeded')
    if set(nodes) != expected:
        errors.append('evaluated topology is incomplete or contains extra nodes')
    terminals = np.zeros(n)
    revenue, cost = 0., 0.
    for path, node in nodes.items():
        feed = vector(node.get('feed'), f'{path}/feed')
        number(node.get('T'), f'{path}/T', positive=True)
        number(node.get('P'), f'{path}/P', positive=True)
        if path == '':
            close(feed, econ.feed, 'root feed')
            for key, target in [('T', econ.T0), ('P', econ.P0)]:
                value = node.get(key)
                if isinstance(value, (int, float)) and not math.isclose(value, target, rel_tol=1e-6, abs_tol=1e-5):
                    errors.append('root ' + key + ': does not match task')
        if path in design:
            if node.get('status') != 'ok':
                errors.append(f'{path}: column not solved ({node.get("status")})')
                continue
            raw = node.get('column_result', {})
            tac = number(raw.get('tac'), f'{path}/cost', nonnegative=True)
            if tac is not None:
                cost += tac
            for duty in ['qc', 'qr']:
                number(raw.get(duty), f'{path}/{duty}')
            outlets = []
            for side, suffix in [('tops','T'), ('bottoms','B')] + ([('side', 'S')] if len(design[path]) > 4 and design[path][4] is not None else []):
                stream = raw.get(side, {})
                flow = vector(stream.get('flows'), f'{path}/{side}')
                number(stream.get('T'), f'{path}/{side}/T', positive=True)
                number(stream.get('P'), f'{path}/{side}/P', positive=True)
                child = nodes.get(path+suffix)
                if child is not None:
                    close(flow, vector(child.get('feed'), f'{path+suffix}/feed'), f'{path}/{side} continuity')
                    for key in ['T', 'P']:
                        x, y = stream.get(key), child.get(key)
                        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-5):
                            errors.append(f'{path}/{side}/{key}: state continuity mismatch')
                outlets.append(flow)
            if all(x is not None for x in outlets):
                close(sum(outlets), feed, f'{path}/component balance')
        else:
            if node.get('status') != 'sold':
                errors.append(f'{path}: unexpected terminal status')
            if feed is not None:
                terminals += feed
                revenue += econ.stream_value(feed)
    close(terminals, econ.feed, 'overall component balance')
    for key, expected_value in [('revenue',revenue),('tac',cost),('reward',(revenue-cost)/econ.reward_norm)]:
        value=number(result.get(key), key)
        if value is not None and not math.isclose(value, expected_value, rel_tol=1e-6, abs_tol=1e-5):
            errors.append(key + ': economic accounting mismatch')
    return {'eligible': not errors, 'errors': errors, 'max_abs_residuals_mol_s': residuals,
            'tolerances': {'absolute_mol_s': atol, 'relative': rtol, 'status': 'provisional'},
            'energy_balance_verified': False}
