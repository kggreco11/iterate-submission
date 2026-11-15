"""Optional column domain rules shared by editing and saved-design validation."""
import math
from sepdesign.multi_effect import FRACTION_BOUNDS

SIDE_PHASES = ('liquid', 'vapour')
SIDE_FRACTION_BOUNDS = (0.02, 0.6)


def optional_settings_errors(spec, task, bounds):
    errors = []
    try:
        side = spec[4] if len(spec) > 4 else None
        effect = spec[5] if len(spec) > 5 else None
        levers = task.get('levers') or {}
        v3 = task['task_id'].startswith('hc16v3_')
        if side is not None:
            if not v3 or not levers.get('side_draw'):
                errors.append('this task has no side draws')
            if not isinstance(side, (list, tuple)) or len(side) != 3:
                errors.append('side_draw must contain stage, phase and fraction')
            else:
                stage, phase, fraction = side
                if (not isinstance(stage, int) or isinstance(stage, bool) or
                    not 2 <= stage <= int(spec[0])-1 or stage == int(round(spec[0]/2))):
                    errors.append('side_draw stage must be internal and not the feed stage')
                if phase not in SIDE_PHASES:
                    errors.append('invalid side_draw phase')
                if not SIDE_FRACTION_BOUNDS[0] <= float(fraction) <= SIDE_FRACTION_BOUNDS[1]:
                    errors.append('side_draw fraction outside bounds')
        if len(spec) == 6:
            if not v3 or not levers.get('double_effect'):
                errors.append('this task has no double-effect columns')
            if side is not None:
                errors.append('a column cannot have both a side draw and a double effect')
            if not isinstance(effect, (list, tuple)) or len(effect) != 2:
                errors.append('double_effect must contain fraction and low-pressure drop')
            else:
                f, dp = map(float, effect)
                if not FRACTION_BOUNDS[0] <= f <= FRACTION_BOUNDS[1]:
                    errors.append('double_effect fraction outside bounds')
                # Compare rounded values without a binary floating-point boundary artifact.
                if not math.isfinite(dp) or dp < round(float(spec[3])+0.01, 2) or dp > bounds['pressure_drop_fraction'][1]:
                    errors.append('double_effect low-pressure drop outside bounds')
    except (KeyError, TypeError, ValueError, OverflowError):
        errors.append('invalid optional column settings')
    return errors
