"""画面下中央に出る「録音中」「変換中」の表示（Mac 専用）。

メニューバー(rumps)と同じ「メイン スレッド」から呼ぶこと。
（Mac では画面の部品を作ったり変えたりできるのはメイン スレッドだけのため）
"""
import AppKit as AK

W, H = 240, 46

# 名前が SDK の版で変わることがあるため、値を直接書く
STYLE_BORDERLESS = 0
STYLE_NONACTIVATING_PANEL = 1 << 7
BACKING_BUFFERED = 2
LEVEL_STATUS = 25
JOIN_ALL_SPACES = 1 << 0
STATIONARY = 1 << 4
FULLSCREEN_AUX = 1 << 8


class Overlay:
    def __init__(self):
        p = AK.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, W, H), STYLE_BORDERLESS | STYLE_NONACTIVATING_PANEL, BACKING_BUFFERED, False
        )
        p.setLevel_(LEVEL_STATUS)                 # 他のウィンドウより手前に出す
        p.setOpaque_(False)
        p.setBackgroundColor_(AK.NSColor.clearColor())
        p.setIgnoresMouseEvents_(True)           # クリックを邪魔しない
        p.setHasShadow_(True)
        p.setHidesOnDeactivate_(False)
        p.setCollectionBehavior_(JOIN_ALL_SPACES | STATIONARY | FULLSCREEN_AUX)

        v = p.contentView()
        v.setWantsLayer_(True)
        v.layer().setCornerRadius_(H / 2)
        v.layer().setBackgroundColor_(AK.NSColor.colorWithCalibratedWhite_alpha_(0.1, 0.9).CGColor())

        label = AK.NSTextField.labelWithString_("")
        label.setFrame_(AK.NSMakeRect(0, (H - 22) / 2, W, 22))
        label.setAlignment_(getattr(AK, "NSTextAlignmentCenter", 1))
        label.setTextColor_(AK.NSColor.whiteColor())
        label.setFont_(AK.NSFont.boldSystemFontOfSize_(16))
        v.addSubview_(label)

        self.panel, self.label = p, label
        self.visible = False

    def show(self, text: str):
        self.label.setStringValue_(text)
        if not self.visible:
            # マウスがある画面の下中央に出す
            screen = AK.NSScreen.mainScreen()
            mouse = AK.NSEvent.mouseLocation()
            for s in AK.NSScreen.screens():
                if AK.NSPointInRect(mouse, s.frame()):
                    screen = s
                    break
            f = screen.visibleFrame()
            self.panel.setFrameOrigin_(AK.NSMakePoint(f.origin.x + (f.size.width - W) / 2, f.origin.y + 90))
            self.panel.orderFrontRegardless()
            self.visible = True

    def hide(self):
        if self.visible:
            self.panel.orderOut_(None)
            self.visible = False
