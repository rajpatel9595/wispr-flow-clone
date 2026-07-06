"""Wispr-style floating capsule shown while recording / transcribing.

A tiny blurred dark pill just above the Dock with an animated 5-bar waveform:
bars bounce while listening, dim and pulse while transcribing. No text.

CRITICAL: every method here calls AppKit and MUST run on the main thread. Only
invoke them from the rumps.Timer callback in main.py — never from the worker or
hotkey listener threads.

The panel is a NON-ACTIVATING NSPanel: showing it must not steal keyboard focus,
otherwise the injector's Cmd+V would paste into this pill instead of the app the
user is actually typing into.
"""
from __future__ import annotations

# Stable AppKit/QuartzCore ABI constants (hardcoded to avoid pyobjc
# version differences in symbol names).
_BORDERLESS = 0
_NONACTIVATING_PANEL = 1 << 7     # NSWindowStyleMaskNonactivatingPanel
_BACKING_BUFFERED = 2             # NSBackingStoreBuffered
_LEVEL_FLOATING = 3               # NSFloatingWindowLevel

_W, _H = 74.0, 28.0
_BAR_W, _GAP = 3.0, 4.0
_BAR_HEIGHTS = (7.0, 12.0, 17.0, 12.0, 7.0)


class Hud:
    def __init__(self) -> None:
        self._panel = None
        self._bars: list = []
        self._mode: str | None = None

    def _build(self) -> None:
        from AppKit import NSColor, NSPanel, NSScreen, NSView
        from Foundation import NSMakeRect

        vis = NSScreen.mainScreen().visibleFrame()
        x = vis.origin.x + (vis.size.width - _W) / 2.0
        y = vis.origin.y + 8.0  # visibleFrame already excludes the Dock
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, _W, _H),
            _BORDERLESS | _NONACTIVATING_PANEL,
            _BACKING_BUFFERED,
            False,
        )
        panel.setLevel_(_LEVEL_FLOATING)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)  # keep focus on the target app

        # Solid black capsule background (like the real Wispr Flow pill).
        effect = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, _W, _H))
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(_H / 2.0)
        effect.layer().setMasksToBounds_(True)
        effect.layer().setBackgroundColor_(
            NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.96).CGColor()
        )
        effect.layer().setBorderWidth_(1.0)
        effect.layer().setBorderColor_(
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.08).CGColor()
        )
        panel.setContentView_(effect)

        # Waveform bars live on an overlay view (the effect view owns its own layer).
        from Quartz import CALayer

        overlay = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, _W, _H))
        overlay.setWantsLayer_(True)
        effect.addSubview_(overlay)

        total = len(_BAR_HEIGHTS) * _BAR_W + (len(_BAR_HEIGHTS) - 1) * _GAP
        x0 = (_W - total) / 2.0
        white = NSColor.whiteColor().CGColor()
        for i, h in enumerate(_BAR_HEIGHTS):
            bar = CALayer.layer()
            bar.setBackgroundColor_(white)
            bar.setCornerRadius_(_BAR_W / 2.0)
            bar.setFrame_(((x0 + i * (_BAR_W + _GAP), (_H - h) / 2.0), (_BAR_W, h)))
            overlay.layer().addSublayer_(bar)
            self._bars.append(bar)

        self._panel = panel

    def _animate(self, mode: str) -> None:
        from Quartz import CABasicAnimation

        for i, bar in enumerate(self._bars):
            bar.removeAllAnimations()
            if mode == "listening":
                anim = CABasicAnimation.animationWithKeyPath_("transform.scale.y")
                anim.setFromValue_(0.3)
                anim.setToValue_(1.0)
                anim.setDuration_(0.38)
                anim.setTimeOffset_(i * 0.11)  # stagger for a rolling-wave look
                bar.setOpacity_(1.0)
            else:  # transcribing: bars hold shape, gently pulse
                anim = CABasicAnimation.animationWithKeyPath_("opacity")
                anim.setFromValue_(0.9)
                anim.setToValue_(0.25)
                anim.setDuration_(0.55)
                anim.setTimeOffset_(i * 0.07)
            anim.setAutoreverses_(True)
            anim.setRepeatCount_(1e9)
            bar.addAnimation_forKey_(anim, "pulse")

    def _show(self, mode: str) -> None:
        if self._panel is None:
            self._build()
        if self._mode != mode:
            self._mode = mode
            self._animate(mode)
        self._panel.orderFront_(None)  # NOT makeKey — must not activate our app

    def listening(self) -> None:
        self._show("listening")

    def busy(self) -> None:
        self._show("busy")

    def hide(self) -> None:
        if self._panel is not None:
            self._panel.orderOut_(None)
            self._mode = None
