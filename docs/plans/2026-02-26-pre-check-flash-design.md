# Pre-Check Green Flash — Design

**Date:** 2026-02-26
**Status:** Approved

## Summary

2 minutes before each scheduled hourly check, the menubar icon turns green for 10 seconds as a visual heads-up, then reverts to the current state icon. Only applies to scheduled hourly checks — not startup, not manual "Check Now."

## Behavior

1. **T-2min**: Icon turns green (new `icon-green.png`, same 22x22 filled circle style)
2. **After 10 seconds**: Icon reverts to current state (gray/blue/red) via `_current_state_icon()` helper
3. **T=0**: Hourly check fires normally
4. **After check**: Icon updates per check results (gray, blue, or red)

## Implementation Guardrails

### 1. Single state-icon function
A `_current_state_icon()` method returns the correct icon path based on current app state (`red` if error, `blue/highlight` if has_new, `gray` otherwise). The flash revert calls this — never hardcodes gray.

### 2. Guard small intervals
If `check_interval_minutes * 60 <= 120` (i.e., interval is 2 minutes or less), skip the pre-flash entirely. The flash lead time must be strictly less than the check interval.

### 3. Flash token/counter
An `_flash_generation` counter increments each time a flash starts. The 10-second revert callback captures the generation value and only applies if it still matches — prevents stale reverts from overriding newer state changes (e.g., if a "Check Now" completes during the flash window).

### 4. Real timer for 10s delay
Use a `rumps.Timer` (or `threading.Timer` + `callAfter`) for the 10-second revert — not `callAfter` alone (which runs ASAP, not after a delay). The revert dispatches to main thread via `callAfter` for the actual UI mutation.

## Files Changed

| File | Change |
|------|--------|
| `icons/icon-green.png` | New 22x22 green filled circle |
| `app.py` | Add `ICON_GREEN` constant, `_current_state_icon()`, `_flash_generation` counter, `_pre_check_flash()`, `_end_flash()`, pre-check timer setup with interval guard |

## Timer Architecture

```
App startup:
  _timer = rumps.Timer(_hourly_check, interval_seconds)       # main check
  _pre_check_timer = rumps.Timer(_pre_check_flash, interval_seconds)  # flash
  _pre_check_timer starts with initial delay = interval_seconds - 120

_pre_check_flash fires:
  if interval_seconds <= 120: return  (guard)
  _flash_generation += 1
  self.icon = ICON_GREEN
  start 10s threading.Timer → callAfter(_end_flash, captured_generation)

_end_flash(generation):
  if generation != _flash_generation: return  (stale guard)
  self.icon = _current_state_icon()
```

## Edge Cases

- **Icon already blue/red when flash fires**: Revert goes back to blue/red via `_current_state_icon()`
- **"Check Now" during flash**: Check results update icon normally; stale revert is no-op (generation mismatch)
- **Interval <= 2 min**: Flash is skipped entirely
- **App just started**: No flash on initial check (pre-check timer hasn't fired yet)

## Tests

- `_current_state_icon()` returns correct icon for each state
- Flash generation guard: stale revert is no-op
- Small interval guard: no flash when interval <= 120s
