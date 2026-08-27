--[[
╔═══════════════════════════════════════════════════╗
║   GREEDY FARM HUB  —  Nha Trong Tham Lam         ║
║   PlaceId : 74102906764176                        ║
║   Features: Lightning Detector + Alert System    ║
╚═══════════════════════════════════════════════════╝
Mobile-safe: no goto, pixel layout
--]]

local Players          = game:GetService("Players")
local TweenService     = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local RunService       = game:GetService("RunService")

local lp   = Players.LocalPlayer
local pg   = lp.PlayerGui
local char = lp.Character or lp.CharacterAdded:Wait()

-- ── PLACE CHECK ───────────────────────────────────────────
local PLACE_ID    = 74102906764176
local SUPPORTED   = game.PlaceId == PLACE_ID

-- ── PALETTE ───────────────────────────────────────────────
local C = {
    bg      = Color3.fromRGB(8,   10,  18),
    panel   = Color3.fromRGB(14,  16,  28),
    card    = Color3.fromRGB(20,  22,  38),
    cardH   = Color3.fromRGB(28,  30,  50),
    border  = Color3.fromRGB(45,  48,  80),
    accent  = Color3.fromRGB(120, 80,  240),
    accentL = Color3.fromRGB(160, 120, 255),
    accentD = Color3.fromRGB(75,  45,  180),
    yellow  = Color3.fromRGB(255, 210, 40),
    gold    = Color3.fromRGB(255, 180, 0),
    green   = Color3.fromRGB(80,  215, 120),
    red     = Color3.fromRGB(235, 70,  70),
    orange  = Color3.fromRGB(255, 140, 30),
    text    = Color3.fromRGB(225, 225, 255),
    sub     = Color3.fromRGB(115, 115, 160),
    white   = Color3.fromRGB(255, 255, 255),
    off_    = Color3.fromRGB(45,  45,  65),
    -- Lightning colors
    bolt    = Color3.fromRGB(255, 240, 80),
    boltGlow= Color3.fromRGB(200, 160, 0),
}

-- ── STATE ─────────────────────────────────────────────────
local STATE = {
    lightningAlert = true,   -- Đoán sét chính
    alertSound     = true,   -- Phát âm thanh cảnh báo
    alertRadius    = 30,     -- Bán kính cây của mình (studs)
    alertTime      = 3,      -- Thông báo trước N giây
}

local menuOpen     = false
local dragging     = false
local dragStart, frameStart
local notifCount   = 0
local alertActive  = false   -- tránh spam notify

-- ══════════════════════════════════════════════════════════
--  TWEEN HELPER
-- ══════════════════════════════════════════════════════════
local function tw(obj, props, t, sty, dir)
    return TweenService:Create(obj,
        TweenInfo.new(t or 0.25,
            sty or Enum.EasingStyle.Quart,
            dir or Enum.EasingDirection.Out),
        props)
end

-- ══════════════════════════════════════════════════════════
--  CLEAN OLD GUI
-- ══════════════════════════════════════════════════════════
for _, g in ipairs(pg:GetChildren()) do
    if g.Name:find("GreedyFarm") then g:Destroy() end
end

-- ══════════════════════════════════════════════════════════
--  LOADING SCREEN
-- ══════════════════════════════════════════════════════════
local loadGui = Instance.new("ScreenGui")
loadGui.Name            = "GreedyFarmLoad"
loadGui.ResetOnSpawn    = false
loadGui.IgnoreGuiInset  = true
loadGui.ZIndexBehavior  = Enum.ZIndexBehavior.Sibling
loadGui.Parent          = pg

-- Full dark overlay
local overlay = Instance.new("Frame")
overlay.Size             = UDim2.fromScale(1, 1)
overlay.BackgroundColor3 = Color3.fromRGB(4, 5, 12)
overlay.BorderSizePixel  = 0
overlay.ZIndex           = 50
overlay.Parent           = loadGui

-- Center container
local loadBox = Instance.new("Frame")
loadBox.Size             = UDim2.new(0, 300, 0, 260)
loadBox.AnchorPoint      = Vector2.new(0.5, 0.5)
loadBox.Position         = UDim2.fromScale(0.5, 0.5)
loadBox.BackgroundColor3 = C.panel
loadBox.BorderSizePixel  = 0
loadBox.ZIndex           = 51
loadBox.Parent           = overlay
Instance.new("UICorner", loadBox).CornerRadius = UDim.new(0, 18)

local loadStroke = Instance.new("UIStroke")
loadStroke.Color       = C.accent
loadStroke.Thickness   = 1.5
loadStroke.Transparency= 0.3
loadStroke.Parent      = loadBox

-- Lightning bolt icon
local boltLbl = Instance.new("TextLabel")
boltLbl.Size   = UDim2.new(1, 0, 0, 70)
boltLbl.Position = UDim2.new(0, 0, 0, 22)
boltLbl.BackgroundTransparency = 1
boltLbl.Text   = "⚡"
boltLbl.TextSize = 52
boltLbl.Font   = Enum.Font.GothamBold
boltLbl.TextColor3 = C.yellow
boltLbl.ZIndex = 52
boltLbl.Parent = loadBox

-- Title
local loadTitle = Instance.new("TextLabel")
loadTitle.Size   = UDim2.new(1, -20, 0, 28)
loadTitle.Position = UDim2.new(0, 10, 0, 98)
loadTitle.BackgroundTransparency = 1
loadTitle.Text   = "GREEDY FARM HUB"
loadTitle.TextColor3 = C.accentL
loadTitle.TextSize = 17
loadTitle.Font   = Enum.Font.GothamBold
loadTitle.ZIndex = 52
loadTitle.Parent = loadBox

-- Subtitle
local loadSub = Instance.new("TextLabel")
loadSub.Size   = UDim2.new(1, -20, 0, 20)
loadSub.Position = UDim2.new(0, 10, 0, 128)
loadSub.BackgroundTransparency = 1
loadSub.Text   = "Nha Trong Tham Lam"
loadSub.TextColor3 = C.sub
loadSub.TextSize = 12
loadSub.Font   = Enum.Font.Gotham
loadSub.ZIndex = 52
loadSub.Parent = loadBox

-- Progress bar BG
local barBg = Instance.new("Frame")
barBg.Size             = UDim2.new(0, 240, 0, 8)
barBg.Position         = UDim2.new(0, 30, 0, 168)
barBg.BackgroundColor3 = C.border
barBg.BorderSizePixel  = 0
barBg.ZIndex           = 52
barBg.Parent           = loadBox
Instance.new("UICorner", barBg).CornerRadius = UDim.new(1, 0)

-- Progress bar fill
local barFill = Instance.new("Frame")
barFill.Size             = UDim2.new(0, 0, 1, 0)
barFill.BackgroundColor3 = C.accent
barFill.BorderSizePixel  = 0
barFill.ZIndex           = 53
barFill.Parent           = barBg
Instance.new("UICorner", barFill).CornerRadius = UDim.new(1, 0)

-- Progress glow
local barGlow = Instance.new("Frame")
barGlow.Size             = UDim2.new(0, 20, 3, 0)
barGlow.AnchorPoint      = Vector2.new(1, 0.5)
barGlow.Position         = UDim2.new(1, 0, 0.5, 0)
barGlow.BackgroundColor3 = C.accentL
barGlow.BackgroundTransparency = 0.5
barGlow.BorderSizePixel  = 0
barGlow.ZIndex           = 54
barGlow.Parent           = barFill
Instance.new("UICorner", barGlow).CornerRadius = UDim.new(1, 0)

-- Status text
local loadStatus = Instance.new("TextLabel")
loadStatus.Size   = UDim2.new(1, -20, 0, 18)
loadStatus.Position = UDim2.new(0, 10, 0, 185)
loadStatus.BackgroundTransparency = 1
loadStatus.Text   = "Khoi dong..."
loadStatus.TextColor3 = C.sub
loadStatus.TextSize = 10
loadStatus.Font   = Enum.Font.Code
loadStatus.ZIndex = 52
loadStatus.Parent = loadBox

-- Version
local verLbl = Instance.new("TextLabel")
verLbl.Size   = UDim2.new(1, -20, 0, 16)
verLbl.Position = UDim2.new(0, 10, 0, 232)
verLbl.BackgroundTransparency = 1
verLbl.Text   = "v1.0  •  by AnimeModHub"
verLbl.TextColor3 = Color3.fromRGB(60, 60, 90)
verLbl.TextSize = 9
verLbl.Font   = Enum.Font.Code
verLbl.ZIndex = 52
verLbl.Parent = loadBox

-- Animate bolt
task.spawn(function()
    while loadGui and loadGui.Parent do
        tw(boltLbl, {TextColor3 = C.gold}, 0.5, Enum.EasingStyle.Sine):Play()
        task.wait(0.6)
        tw(boltLbl, {TextColor3 = C.yellow}, 0.5, Enum.EasingStyle.Sine):Play()
        task.wait(0.6)
    end
end)

-- Loading steps
local steps = {
    {0.12, "Ket noi game..."},
    {0.28, "Doc du lieu cay trong..."},
    {0.45, "Khoi tao he thong Set..."},
    {0.62, "Ket noi he thong canh bao..."},
    {0.78, "Kiem tra nguoi choi..."},
    {0.90, "Chuan bi giao dien..."},
    {1.00, "Hoan tat! Chuc vui!"},
}

for _, step in ipairs(steps) do
    tw(barFill, {Size = UDim2.new(step[1], 0, 1, 0)}, 0.35, Enum.EasingStyle.Quart):Play()
    loadStatus.Text = step[2]
    task.wait(0.38)
end

task.wait(0.3)
-- Fade out loading
tw(overlay, {BackgroundTransparency = 1}, 0.5):Play()
tw(loadBox, {BackgroundTransparency = 1}, 0.5):Play()
tw(loadTitle, {TextTransparency = 1}, 0.4):Play()
tw(loadSub,   {TextTransparency = 1}, 0.4):Play()
tw(loadStatus,{TextTransparency = 1}, 0.4):Play()
tw(boltLbl,   {TextTransparency = 1}, 0.4):Play()
tw(barBg,     {BackgroundTransparency = 1}, 0.4):Play()
tw(verLbl,    {TextTransparency = 1}, 0.4):Play()
task.delay(0.55, function() pcall(function() loadGui:Destroy() end) end)

-- ══════════════════════════════════════════════════════════
--  NOTIFICATION GUI
-- ══════════════════════════════════════════════════════════
local notifGui = Instance.new("ScreenGui")
notifGui.Name           = "GreedyFarmNotif"
notifGui.ResetOnSpawn   = false
notifGui.IgnoreGuiInset = true
notifGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
notifGui.Parent         = pg

local notifHolder = Instance.new("Frame")
notifHolder.Size              = UDim2.new(0, 300, 1, 0)
notifHolder.AnchorPoint       = Vector2.new(1, 1)
notifHolder.Position          = UDim2.new(1, -10, 1, -10)
notifHolder.BackgroundTransparency = 1
notifHolder.Parent            = notifGui

local notifList = Instance.new("UIListLayout")
notifList.SortOrder         = Enum.SortOrder.LayoutOrder
notifList.VerticalAlignment = Enum.VerticalAlignment.Bottom
notifList.Padding           = UDim.new(0, 6)
notifList.Parent            = notifHolder

local function notify(title, body, kind, duration)
    kind     = kind or "info"
    duration = duration or 4
    local ic = (kind=="lightning" and C.yellow)
            or (kind=="success"   and C.green)
            or (kind=="warn"      and C.orange)
            or (kind=="error"     and C.red)
            or C.accentL
    notifCount = notifCount + 1

    local ncard = Instance.new("Frame")
    ncard.Size             = UDim2.new(1, 0, 0, kind=="lightning" and 80 or 62)
    ncard.BackgroundColor3 = C.panel
    ncard.BorderSizePixel  = 0
    ncard.LayoutOrder      = notifCount
    ncard.Parent           = notifHolder
    Instance.new("UICorner", ncard).CornerRadius = UDim.new(0, 11)

    -- Glow stroke for lightning
    local nstroke = Instance.new("UIStroke")
    nstroke.Color       = ic
    nstroke.Thickness   = kind=="lightning" and 1.5 or 1
    nstroke.Transparency= kind=="lightning" and 0.1 or 0.6
    nstroke.Parent      = ncard

    -- Strip
    local strip = Instance.new("Frame")
    strip.Size             = UDim2.new(0, 4, 1, -8)
    strip.Position         = UDim2.new(0, 0, 0, 4)
    strip.BackgroundColor3 = ic
    strip.BorderSizePixel  = 0
    strip.Parent           = ncard
    Instance.new("UICorner", strip).CornerRadius = UDim.new(0, 3)

    -- Icon
    local icon = Instance.new("TextLabel")
    icon.Size  = UDim2.new(0, 32, 0, 32)
    icon.Position = UDim2.new(0, 10, 0.5, -16)
    icon.BackgroundTransparency = 1
    icon.Text  = kind=="lightning" and "⚡" or
                 kind=="success"   and "✅" or
                 kind=="warn"      and "⚠️" or
                 kind=="error"     and "❌" or "ℹ️"
    icon.TextSize = kind=="lightning" and 26 or 20
    icon.Font  = Enum.Font.GothamBold
    icon.ZIndex = 5; icon.Parent = ncard

    -- Title
    local tl = Instance.new("TextLabel")
    tl.Size  = UDim2.new(1, -52, 0, kind=="lightning" and 24 or 20)
    tl.Position = UDim2.new(0, 48, 0, kind=="lightning" and 10 or 8)
    tl.BackgroundTransparency = 1
    tl.Text  = title
    tl.TextColor3 = kind=="lightning" and C.yellow or C.white
    tl.TextSize = kind=="lightning" and 13 or 12
    tl.Font  = Enum.Font.GothamBold
    tl.TextXAlignment = Enum.TextXAlignment.Left
    tl.ZIndex = 5; tl.Parent = ncard

    -- Body
    local bl = Instance.new("TextLabel")
    bl.Size  = UDim2.new(1, -52, 0, kind=="lightning" and 36 or 26)
    bl.Position = UDim2.new(0, 48, 0, kind=="lightning" and 36 or 30)
    bl.BackgroundTransparency = 1
    bl.Text  = body
    bl.TextColor3 = kind=="lightning" and C.gold or C.sub
    bl.TextSize = kind=="lightning" and 11 or 10
    bl.Font  = kind=="lightning" and Enum.Font.GothamBold or Enum.Font.Gotham
    bl.TextXAlignment = Enum.TextXAlignment.Left
    bl.TextWrapped = true
    bl.ZIndex = 5; bl.Parent = ncard

    -- Slide in
    ncard.Position = UDim2.new(1, 10, 0, 0)
    tw(ncard, {Position = UDim2.new(0,0,0,0)}, 0.28, Enum.EasingStyle.Back):Play()

    -- Lightning: flash border
    if kind == "lightning" then
        task.spawn(function()
            for _ = 1, 4 do
                tw(nstroke, {Transparency = 0.8}, 0.2, Enum.EasingStyle.Sine):Play()
                task.wait(0.22)
                tw(nstroke, {Transparency = 0.0}, 0.2, Enum.EasingStyle.Sine):Play()
                task.wait(0.22)
            end
        end)
    end

    -- Auto remove
    task.delay(duration, function()
        if not ncard.Parent then return end
        tw(ncard,  {BackgroundTransparency = 1}, 0.28):Play()
        tw(tl,     {TextTransparency = 1}, 0.28):Play()
        tw(bl,     {TextTransparency = 1}, 0.28):Play()
        tw(icon,   {TextTransparency = 1}, 0.28):Play()
        tw(strip,  {BackgroundTransparency = 1}, 0.28):Play()
        tw(nstroke,{Transparency = 1}, 0.28):Play()
        task.delay(0.32, function() pcall(function() ncard:Destroy() end) end)
    end)
end

-- ══════════════════════════════════════════════════════════
--  LIGHTNING ALERT OVERLAY (full screen flash)
-- ══════════════════════════════════════════════════════════
local alertGui = Instance.new("ScreenGui")
alertGui.Name           = "GreedyFarmAlert"
alertGui.ResetOnSpawn   = false
alertGui.IgnoreGuiInset = true
alertGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
alertGui.Parent         = pg

local alertOverlay = Instance.new("Frame")
alertOverlay.Size             = UDim2.fromScale(1, 1)
alertOverlay.BackgroundColor3 = C.yellow
alertOverlay.BackgroundTransparency = 1
alertOverlay.BorderSizePixel  = 0
alertOverlay.ZIndex           = 40
alertOverlay.Visible          = false
alertOverlay.Parent           = alertGui

-- Big warning text
local alertBig = Instance.new("TextLabel")
alertBig.Size   = UDim2.new(1, 0, 0, 80)
alertBig.AnchorPoint = Vector2.new(0.5, 0.5)
alertBig.Position = UDim2.fromScale(0.5, 0.38)
alertBig.BackgroundTransparency = 1
alertBig.Text   = "⚡  SÉT SẮP ĐÁNH!  ⚡"
alertBig.TextColor3 = C.yellow
alertBig.TextSize = 34
alertBig.Font   = Enum.Font.GothamBold
alertBig.TextStrokeColor3 = Color3.fromRGB(0,0,0)
alertBig.TextStrokeTransparency = 0.2
alertBig.ZIndex = 41
alertBig.Visible = false
alertBig.Parent = alertGui

local alertSub = Instance.new("TextLabel")
alertSub.Size   = UDim2.new(1, 0, 0, 40)
alertSub.AnchorPoint = Vector2.new(0.5, 0.5)
alertSub.Position = UDim2.fromScale(0.5, 0.50)
alertSub.BackgroundTransparency = 1
alertSub.Text   = ""
alertSub.TextColor3 = C.white
alertSub.TextSize = 16
alertSub.Font   = Enum.Font.GothamBold
alertSub.TextStrokeColor3 = Color3.fromRGB(0,0,0)
alertSub.TextStrokeTransparency = 0.1
alertSub.ZIndex = 41
alertSub.Visible = false
alertSub.Parent = alertGui

local function flashAlert(playerName, treeName)
    if alertActive then return end
    alertActive = true

    alertSub.Text   = playerName .. " — Cay cua ban sap bi set danh!"
    alertOverlay.Visible = true
    alertBig.Visible     = true
    alertSub.Visible     = true

    -- Flash screen 3 times
    for _ = 1, 3 do
        tw(alertOverlay, {BackgroundTransparency = 0.75}, 0.18, Enum.EasingStyle.Sine):Play()
        task.wait(0.2)
        tw(alertOverlay, {BackgroundTransparency = 1}, 0.18, Enum.EasingStyle.Sine):Play()
        task.wait(0.2)
    end

    task.delay(3, function()
        alertOverlay.Visible = false
        alertBig.Visible     = false
        alertSub.Visible     = false
        alertActive = false
    end)
end

-- ══════════════════════════════════════════════════════════
--  MAIN GUI
-- ══════════════════════════════════════════════════════════
local mainGui = Instance.new("ScreenGui")
mainGui.Name            = "GreedyFarmMain"
mainGui.ResetOnSpawn    = false
mainGui.IgnoreGuiInset  = true
mainGui.ZIndexBehavior  = Enum.ZIndexBehavior.Sibling
mainGui.Parent          = pg

-- ── CIRCULAR TOGGLE BUTTON ────────────────────────────────
local circleBtn = Instance.new("TextButton")
circleBtn.Size             = UDim2.new(0, 52, 0, 52)
circleBtn.AnchorPoint      = Vector2.new(0.5, 0.5)
circleBtn.Position         = UDim2.new(1, -38, 0.5, 0)
circleBtn.BackgroundColor3 = C.accentD
circleBtn.BorderSizePixel  = 0
circleBtn.Text             = "⚡"
circleBtn.TextSize         = 22
circleBtn.TextColor3       = C.yellow
circleBtn.Font             = Enum.Font.GothamBold
circleBtn.AutoButtonColor  = false
circleBtn.ZIndex           = 30
circleBtn.Parent           = mainGui
Instance.new("UICorner", circleBtn).CornerRadius = UDim.new(1, 0)

-- Circle stroke pulse
local circleStroke = Instance.new("UIStroke")
circleStroke.Color       = C.yellow
circleStroke.Thickness   = 2
circleStroke.Transparency= 0.2
circleStroke.Parent      = circleBtn

-- Inner glow ring
local circleGlow = Instance.new("Frame")
circleGlow.Size             = UDim2.new(0, 64, 0, 64)
circleGlow.AnchorPoint      = Vector2.new(0.5, 0.5)
circleGlow.Position         = UDim2.fromScale(0.5, 0.5)
circleGlow.BackgroundColor3 = C.accent
circleGlow.BackgroundTransparency = 0.75
circleGlow.BorderSizePixel  = 0
circleGlow.ZIndex           = 29
circleGlow.Parent           = circleBtn
Instance.new("UICorner", circleGlow).CornerRadius = UDim.new(1, 0)

-- Pulse animation
task.spawn(function()
    while mainGui and mainGui.Parent do
        tw(circleBtn,  {BackgroundColor3 = C.accent}, 0.8, Enum.EasingStyle.Sine):Play()
        tw(circleStroke,{Transparency = 0.6}, 0.8, Enum.EasingStyle.Sine):Play()
        tw(circleGlow, {BackgroundTransparency = 0.88}, 0.8, Enum.EasingStyle.Sine):Play()
        task.wait(0.9)
        tw(circleBtn,  {BackgroundColor3 = C.accentD}, 0.8, Enum.EasingStyle.Sine):Play()
        tw(circleStroke,{Transparency = 0.15}, 0.8, Enum.EasingStyle.Sine):Play()
        tw(circleGlow, {BackgroundTransparency = 0.72}, 0.8, Enum.EasingStyle.Sine):Play()
        task.wait(0.9)
    end
end)

-- Drag circle button
local cDragging, cDragStart, cPosStart = false, nil, nil
circleBtn.InputBegan:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        cDragging  = true
        cDragStart = inp.Position
        cPosStart  = circleBtn.Position
    end
end)
UserInputService.InputChanged:Connect(function(inp)
    if not cDragging then return end
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseMovement then
        local d = inp.Position - cDragStart
        circleBtn.Position = UDim2.new(
            cPosStart.X.Scale, cPosStart.X.Offset + d.X,
            cPosStart.Y.Scale, cPosStart.Y.Offset + d.Y)
        circleGlow.Position = UDim2.fromScale(0.5, 0.5)
    end
end)
UserInputService.InputEnded:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        cDragging = false
    end
end)

-- ── HORIZONTAL MENU ───────────────────────────────────────
local MENU_W = 540
local MENU_H = 240

local menuFrame = Instance.new("Frame")
menuFrame.Name             = "MenuFrame"
menuFrame.Size             = UDim2.new(0, MENU_W, 0, MENU_H)
menuFrame.AnchorPoint      = Vector2.new(0.5, 0.5)
menuFrame.Position         = UDim2.fromScale(0.5, 0.5)
menuFrame.BackgroundColor3 = C.bg
menuFrame.BorderSizePixel  = 0
menuFrame.Visible          = false
menuFrame.ClipsDescendants = false
menuFrame.ZIndex           = 20
menuFrame.Parent           = mainGui
Instance.new("UICorner", menuFrame).CornerRadius = UDim.new(0, 15)

local menuStroke = Instance.new("UIStroke")
menuStroke.Color       = C.accent
menuStroke.Thickness   = 1.5
menuStroke.Transparency= 0.4
menuStroke.Parent      = menuFrame

-- Header
local mHeader = Instance.new("Frame")
mHeader.Size             = UDim2.new(1, 0, 0, 46)
mHeader.BackgroundColor3 = C.panel
mHeader.BorderSizePixel  = 0
mHeader.ZIndex           = 21
mHeader.Parent           = menuFrame
-- top corners only via UICorner on parent clipping
Instance.new("UICorner", mHeader).CornerRadius = UDim.new(0, 15)

local mHFix = Instance.new("Frame")  -- fix bottom of header
mHFix.Size             = UDim2.new(1, 0, 0, 15)
mHFix.Position         = UDim2.new(0, 0, 1, -15)
mHFix.BackgroundColor3 = C.panel
mHFix.BorderSizePixel  = 0
mHFix.ZIndex           = 21
mHFix.Parent           = mHeader

-- Header icon + title
local mIconLbl = Instance.new("TextLabel")
mIconLbl.Size   = UDim2.new(0, 30, 1, 0)
mIconLbl.Position = UDim2.new(0, 10, 0, 0)
mIconLbl.BackgroundTransparency = 1
mIconLbl.Text   = "⚡"
mIconLbl.TextSize = 20
mIconLbl.Font   = Enum.Font.GothamBold
mIconLbl.TextColor3 = C.yellow
mIconLbl.ZIndex = 22; mIconLbl.Parent = mHeader

local mTitleLbl = Instance.new("TextLabel")
mTitleLbl.Size   = UDim2.new(0, 200, 1, 0)
mTitleLbl.Position = UDim2.new(0, 44, 0, 0)
mTitleLbl.BackgroundTransparency = 1
mTitleLbl.Text   = "Greedy Farm Hub"
mTitleLbl.TextColor3 = C.text; mTitleLbl.TextSize = 13
mTitleLbl.Font   = Enum.Font.GothamBold
mTitleLbl.TextXAlignment = Enum.TextXAlignment.Left
mTitleLbl.ZIndex = 22; mTitleLbl.Parent = mHeader

-- Player name display
local mPlayerLbl = Instance.new("TextLabel")
mPlayerLbl.Size   = UDim2.new(0, 180, 1, 0)
mPlayerLbl.AnchorPoint = Vector2.new(1, 0)
mPlayerLbl.Position = UDim2.new(1, -44, 0, 0)
mPlayerLbl.BackgroundTransparency = 1
mPlayerLbl.Text   = "👤 " .. lp.DisplayName
mPlayerLbl.TextColor3 = C.accentL; mPlayerLbl.TextSize = 11
mPlayerLbl.Font   = Enum.Font.Gotham
mPlayerLbl.TextXAlignment = Enum.TextXAlignment.Right
mPlayerLbl.ZIndex = 22; mPlayerLbl.Parent = mHeader

-- Close menu button
local mCloseBtn = Instance.new("TextButton")
mCloseBtn.Size           = UDim2.new(0, 26, 0, 26)
mCloseBtn.AnchorPoint    = Vector2.new(1, 0.5)
mCloseBtn.Position       = UDim2.new(1, -8, 0.5, 0)
mCloseBtn.BackgroundColor3 = Color3.fromRGB(55,16,16)
mCloseBtn.BorderSizePixel = 0
mCloseBtn.Text           = "✕"
mCloseBtn.TextColor3     = C.red; mCloseBtn.TextSize = 12
mCloseBtn.Font           = Enum.Font.GothamBold
mCloseBtn.AutoButtonColor = false
mCloseBtn.ZIndex         = 23; mCloseBtn.Parent = mHeader
Instance.new("UICorner", mCloseBtn).CornerRadius = UDim.new(0, 6)

-- Drag menu
mHeader.InputBegan:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging   = true
        dragStart  = inp.Position
        frameStart = menuFrame.Position
    end
end)
UserInputService.InputChanged:Connect(function(inp)
    if not dragging then return end
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseMovement then
        local d = inp.Position - dragStart
        menuFrame.Position = UDim2.new(
            frameStart.X.Scale, frameStart.X.Offset + d.X,
            frameStart.Y.Scale, frameStart.Y.Offset + d.Y)
    end
end)
UserInputService.InputEnded:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging = false
    end
end)

mCloseBtn.MouseButton1Click:Connect(function()
    menuOpen = false
    tw(menuFrame, {Size=UDim2.new(0,0,0,0)}, 0.22, Enum.EasingStyle.Back, Enum.EasingDirection.In):Play()
    task.delay(0.25, function() menuFrame.Visible = false end)
    circleBtn.Text = "⚡"
end)

-- ── CONTENT AREA ──────────────────────────────────────────
local mContent = Instance.new("Frame")
mContent.Size             = UDim2.new(0, MENU_W-24, 0, MENU_H-60)
mContent.Position         = UDim2.new(0, 12, 0, 54)
mContent.BackgroundTransparency = 1
mContent.ZIndex           = 21
mContent.Parent           = menuFrame

-- ── LIGHTNING TOGGLE CARD ─────────────────────────────────
-- Large featured card
local ltCard = Instance.new("Frame")
ltCard.Size             = UDim2.new(0, MENU_W-24, 0, 110)
ltCard.Position         = UDim2.new(0, 0, 0, 0)
ltCard.BackgroundColor3 = C.card
ltCard.BorderSizePixel  = 0
ltCard.ZIndex           = 22
ltCard.Parent           = mContent
Instance.new("UICorner", ltCard).CornerRadius = UDim.new(0, 12)

local ltStroke = Instance.new("UIStroke")
ltStroke.Color       = STATE.lightningAlert and C.yellow or C.border
ltStroke.Thickness   = 1.5
ltStroke.Transparency= STATE.lightningAlert and 0.1 or 0.5
ltStroke.Parent      = ltCard

-- Icon
local ltIcon = Instance.new("TextLabel")
ltIcon.Size  = UDim2.new(0, 56, 0, 56)
ltIcon.Position = UDim2.new(0, 14, 0.5, -28)
ltIcon.BackgroundColor3 = Color3.fromRGB(30, 28, 8)
ltIcon.BorderSizePixel = 0
ltIcon.Text  = "⚡"
ltIcon.TextSize = 30; ltIcon.Font = Enum.Font.GothamBold
ltIcon.TextColor3 = C.yellow; ltIcon.ZIndex = 23; ltIcon.Parent = ltCard
Instance.new("UICorner", ltIcon).CornerRadius = UDim.new(0, 10)

-- Name
local ltName = Instance.new("TextLabel")
ltName.Size  = UDim2.new(0, 300, 0, 24)
ltName.Position = UDim2.new(0, 80, 0, 18)
ltName.BackgroundTransparency = 1
ltName.Text  = "Doan Set — Lightning Detector"
ltName.TextColor3 = C.yellow; ltName.TextSize = 14; ltName.Font = Enum.Font.GothamBold
ltName.TextXAlignment = Enum.TextXAlignment.Left
ltName.ZIndex = 23; ltName.Parent = ltCard

-- Desc line 1
local ltDesc1 = Instance.new("TextLabel")
ltDesc1.Size  = UDim2.new(0, 350, 0, 18)
ltDesc1.Position = UDim2.new(0, 80, 0, 44)
ltDesc1.BackgroundTransparency = 1
ltDesc1.Text  = "+ Tu dong kiem tra set sap danh cay"
ltDesc1.TextColor3 = C.sub; ltDesc1.TextSize = 10; ltDesc1.Font = Enum.Font.Gotham
ltDesc1.TextXAlignment = Enum.TextXAlignment.Left
ltDesc1.ZIndex = 23; ltDesc1.Parent = ltCard

-- Desc line 2
local ltDesc2 = Instance.new("TextLabel")
ltDesc2.Size  = UDim2.new(0, 350, 0, 18)
ltDesc2.Position = UDim2.new(0, 80, 0, 62)
ltDesc2.BackgroundTransparency = 1
ltDesc2.Text  = "+ Thong bao truoc " .. STATE.alertTime .. " giay — hien ten nhan vat"
ltDesc2.TextColor3 = C.sub; ltDesc2.TextSize = 10; ltDesc2.Font = Enum.Font.Gotham
ltDesc2.TextXAlignment = Enum.TextXAlignment.Left
ltDesc2.ZIndex = 23; ltDesc2.Parent = ltCard

-- Status badge
local ltBadge = Instance.new("Frame")
ltBadge.Size             = UDim2.new(0, 72, 0, 22)
ltBadge.AnchorPoint      = Vector2.new(0, 1)
ltBadge.Position         = UDim2.new(0, 80, 1, -12)
ltBadge.BackgroundColor3 = STATE.lightningAlert and Color3.fromRGB(30,50,20) or Color3.fromRGB(40,20,20)
ltBadge.BorderSizePixel  = 0; ltBadge.ZIndex = 23; ltBadge.Parent = ltCard
Instance.new("UICorner", ltBadge).CornerRadius = UDim.new(0, 5)

local ltBadgeTxt = Instance.new("TextLabel")
ltBadgeTxt.Size  = UDim2.fromScale(1,1); ltBadgeTxt.BackgroundTransparency = 1
ltBadgeTxt.Text  = STATE.lightningAlert and "● DANG BAT" or "● DA TAT"
ltBadgeTxt.TextColor3 = STATE.lightningAlert and C.green or C.red
ltBadgeTxt.TextSize = 9; ltBadgeTxt.Font = Enum.Font.GothamBold
ltBadgeTxt.ZIndex = 24; ltBadgeTxt.Parent = ltBadge

-- Toggle switch
local ltTrack = Instance.new("Frame")
ltTrack.Size           = UDim2.new(0, 46, 0, 24)
ltTrack.AnchorPoint    = Vector2.new(1, 0.5)
ltTrack.Position       = UDim2.new(1, -14, 0.5, 0)
ltTrack.BackgroundColor3 = STATE.lightningAlert and C.yellow or C.off_
ltTrack.BorderSizePixel = 0; ltTrack.ZIndex = 23; ltTrack.Parent = ltCard
Instance.new("UICorner", ltTrack).CornerRadius = UDim.new(1, 0)

local ltThumb = Instance.new("Frame")
ltThumb.Size           = UDim2.new(0, 18, 0, 18)
ltThumb.AnchorPoint    = Vector2.new(0, 0.5)
ltThumb.Position       = STATE.lightningAlert and UDim2.new(0,25,0.5,0) or UDim2.new(0,3,0.5,0)
ltThumb.BackgroundColor3 = C.white; ltThumb.BorderSizePixel = 0
ltThumb.ZIndex = 24; ltThumb.Parent = ltTrack
Instance.new("UICorner", ltThumb).CornerRadius = UDim.new(1, 0)

local ltBtn = Instance.new("TextButton")
ltBtn.Size  = UDim2.fromScale(1,1); ltBtn.BackgroundTransparency = 1
ltBtn.Text  = ""; ltBtn.ZIndex = 25; ltBtn.AutoButtonColor = false
ltBtn.Parent = ltCard

ltBtn.MouseButton1Click:Connect(function()
    if not SUPPORTED then
        notify("Khong ho tro", "Game nay chua duoc ho tro.", "error")
        return
    end
    STATE.lightningAlert = not STATE.lightningAlert
    local on = STATE.lightningAlert
    tw(ltTrack, {BackgroundColor3 = on and C.yellow or C.off_}, 0.16):Play()
    tw(ltThumb, {Position = on and UDim2.new(0,25,0.5,0) or UDim2.new(0,3,0.5,0)},
       0.16, Enum.EasingStyle.Back):Play()
    tw(ltStroke, {Color = on and C.yellow or C.border,
                  Transparency = on and 0.1 or 0.5}, 0.16):Play()
    ltBadge.BackgroundColor3 = on and Color3.fromRGB(30,50,20) or Color3.fromRGB(40,20,20)
    ltBadgeTxt.Text          = on and "● DANG BAT" or "● DA TAT"
    ltBadgeTxt.TextColor3    = on and C.green or C.red
    notify(
        on and "⚡ Doan Set BAT" or "⚡ Doan Set TAT",
        on and "Dang theo doi set danh vao cay cua ban" or "Da tat theo doi set",
        on and "success" or "info")
end)

ltBtn.MouseEnter:Connect(function()
    tw(ltCard, {BackgroundColor3 = C.cardH}, 0.1):Play()
end)
ltBtn.MouseLeave:Connect(function()
    tw(ltCard, {BackgroundColor3 = C.card}, 0.1):Play()
end)

-- Footer info row
local footerRow = Instance.new("Frame")
footerRow.Size             = UDim2.new(0, MENU_W-24, 0, 28)
footerRow.Position         = UDim2.new(0, 0, 0, 118)
footerRow.BackgroundTransparency = 1
footerRow.ZIndex           = 22
footerRow.Parent           = mContent

local ftPlaceId = Instance.new("TextLabel")
ftPlaceId.Size  = UDim2.new(0.5, 0, 1, 0)
ftPlaceId.BackgroundTransparency = 1
ftPlaceId.Text  = "PlaceId: " .. tostring(game.PlaceId)
ftPlaceId.TextColor3 = C.sub; ftPlaceId.TextSize = 9; ftPlaceId.Font = Enum.Font.Code
ftPlaceId.TextXAlignment = Enum.TextXAlignment.Left
ftPlaceId.ZIndex = 23; ftPlaceId.Parent = footerRow

local ftStatus = Instance.new("TextLabel")
ftStatus.Size   = UDim2.new(0.5, 0, 1, 0)
ftStatus.AnchorPoint = Vector2.new(1, 0)
ftStatus.Position = UDim2.new(1, 0, 0, 0)
ftStatus.BackgroundTransparency = 1
ftStatus.Text   = SUPPORTED and ("● " .. "Nha Trong Tham Lam") or "● Khong ho tro"
ftStatus.TextColor3 = SUPPORTED and C.green or C.red
ftStatus.TextSize = 9; ftStatus.Font = Enum.Font.Code
ftStatus.TextXAlignment = Enum.TextXAlignment.Right
ftStatus.ZIndex = 23; ftStatus.Parent = footerRow

-- ── TOGGLE MENU OPEN/CLOSE ────────────────────────────────
circleBtn.MouseButton1Click:Connect(function()
    menuOpen = not menuOpen
    if menuOpen then
        menuFrame.Visible = true
        menuFrame.Size    = UDim2.new(0, 0, 0, 0)
        tw(menuFrame, {Size = UDim2.new(0, MENU_W, 0, MENU_H)},
           0.3, Enum.EasingStyle.Back, Enum.EasingDirection.Out):Play()
        circleBtn.Text = "✕"
    else
        tw(menuFrame, {Size = UDim2.new(0, 0, 0, 0)},
           0.22, Enum.EasingStyle.Back, Enum.EasingDirection.In):Play()
        task.delay(0.25, function() menuFrame.Visible = false end)
        circleBtn.Text = "⚡"
    end
end)

-- ══════════════════════════════════════════════════════════
--  SMART LIGHTNING DETECTION ENGINE v2
-- ══════════════════════════════════════════════════════════
--[[
    Nguyên tắc v2:
    1) KHÔNG báo sét chỉ vì hub vừa load.
    2) Detector chỉ "ARMED" khi phát hiện ít nhất 1 cây THẬT
       thuộc plot của người chơi.
    3) Không dùng "mọi Neon/Particle = sét" vì gây false-positive.
    4) Khi effect sét xuất hiện, tìm cây gần nhất rồi suy ra OWNER
       từ plot/attributes/model để báo đúng người.
    5) Có cooldown + fingerprint để tránh báo trùng do một effect
       có nhiều descendant.
--]]

local myPlot              = nil
local myTrees             = {}
local detectorArmed       = false
local treeScanStamp       = 0
local treeScanInterval    = 0.35
local allTreesCache        = {}
local allTreeScanStamp     = 0
local allTreeScanInterval  = 1.0
local detectedKeys        = {}
local alertCooldown       = {}
local lightningConnection = nil

local function safeString(v)
    if v == nil then return "" end
    return tostring(v):lower()
end

-- ── OWNER HELPERS ──────────────────────────────────────────
local function valueOwnerName(v)
    if v == nil then return nil end

    if typeof(v) == "Instance" then
        if v:IsA("Player") then
            return v.Name
        end
        return v.Name
    end

    local s = tostring(v)
    if s == "" then return nil end

    -- Có thể server lưu UserId dưới dạng number/string.
    local id = tonumber(s)
    if id then
        local ok, p = pcall(function()
            return Players:GetPlayerByUserId(id)
        end)
        if ok and p then
            return p.Name
        end
    end

    return s
end

local function getOwnerFromAttributes(obj)
    if not obj then return nil end

    local keys = {
        "Owner", "OwnerName", "Player", "PlayerName",
        "Username", "UserName", "OwnerUserId", "PlayerUserId",
        "UserId", "PlotOwner", "FarmOwner"
    }

    for _, key in ipairs(keys) do
        local ok, value = pcall(function()
            return obj:GetAttribute(key)
        end)

        if ok and value ~= nil then
            local owner = valueOwnerName(value)
            if owner and owner ~= "" then
                return owner
            end
        end
    end

    return nil
end

local function findOwnerInAncestors(obj)
    local cur = obj

    for _ = 1, 10 do
        if not cur then break end

        local owner = getOwnerFromAttributes(cur)
        if owner then return owner end

        -- Một số game đặt Player object trực tiếp trong plot.
        for _, child in ipairs(cur:GetChildren()) do
            if child:IsA("ObjectValue") then
                local n = safeString(child.Name)
                if n:find("owner") or n:find("player") then
                    local ok, value = pcall(function() return child.Value end)
                    if ok and value then
                        local resolved = valueOwnerName(value)
                        if resolved then return resolved end
                    end
                end
            end
        end

        if cur.Name == lp.Name or cur.Name == lp.DisplayName then
            return lp.Name
        end

        cur = cur.Parent
    end

    return nil
end

local function ownerMatchesLocal(owner)
    if not owner then return false end

    local a = safeString(owner)
    local b = safeString(lp.Name)
    local c = safeString(lp.DisplayName)

    return a == b or a == c
end

-- ── FIND MY PLOT ───────────────────────────────────────────
local function findMyPlot()
    if myPlot and myPlot.Parent then
        local owner = findOwnerInAncestors(myPlot)
        if ownerMatchesLocal(owner) or myPlot.Name == lp.Name
            or myPlot.Name == lp.DisplayName then
            return myPlot
        end
    end

    local folders = {
        workspace:FindFirstChild("Plots"),
        workspace:FindFirstChild("Farms"),
        workspace:FindFirstChild("PlayerPlots"),
        workspace:FindFirstChild("Gardens"),
        workspace:FindFirstChild("Islands")
    }

    for _, folder in ipairs(folders) do
        if folder then
            for _, plot in ipairs(folder:GetChildren()) do
                if plot.Name == lp.Name or plot.Name == lp.DisplayName then
                    myPlot = plot
                    return plot
                end

                local owner = getOwnerFromAttributes(plot)
                if ownerMatchesLocal(owner) then
                    myPlot = plot
                    return plot
                end
            end
        end
    end

    -- Fallback: tìm object có owner của local player,
    -- nhưng KHÔNG coi toàn workspace là plot.
    for _, obj in ipairs(workspace:GetDescendants()) do
        local owner = getOwnerFromAttributes(obj)
        if ownerMatchesLocal(owner) then
            local candidate = obj
            for _ = 1, 4 do
                if not candidate.Parent or candidate == workspace then break end
                candidate = candidate.Parent
            end

            if candidate and candidate ~= workspace then
                myPlot = candidate
                return candidate
            end
        end
    end

    return nil
end

-- ── TREE CLASSIFICATION ───────────────────────────────────
local TREE_WORDS = {
    "tree", "plant", "crop", "fruit", "flower",
    "farmplant", "grown", "growing", "harvest",
    "cay", "trong", "qua", "hoa"
}

local function looksLikeTreeName(name)
    local n = safeString(name)

    for _, word in ipairs(TREE_WORDS) do
        if n:find(word, 1, true) then
            return true
        end
    end

    return false
end

local function getWorldPosition(obj)
    if not obj then return nil end

    if obj:IsA("BasePart") then
        return obj.Position
    elseif obj:IsA("Attachment") then
        return obj.WorldPosition
    elseif obj:IsA("Model") then
        local ok, pivot = pcall(function()
            return obj:GetPivot()
        end)
        if ok and pivot then
            return pivot.Position
        end
    end

    return nil
end

local function isTreeObject(obj)
    if not obj then return false end
    if not (obj:IsA("Model") or obj:IsA("BasePart") or obj:IsA("Folder")) then
        return false
    end

    local n = safeString(obj.Name)
    if not looksLikeTreeName(n) then return false end

    -- Loại những object rõ ràng là seed/item/inventory.
    if n:find("seedbag") or n:find("seed_shop")
        or n:find("inventory") or n:find("button") then
        return false
    end

    return getWorldPosition(obj) ~= nil
end

local function collectTrees(root, out, onlyLocal)
    if not root then return end

    local seen = {}

    local function add(obj)
        if seen[obj] or not isTreeObject(obj) then return end
        seen[obj] = true

        local pos = getWorldPosition(obj)
        if not pos then return end

        local owner = findOwnerInAncestors(obj)

        -- Nếu biết owner thì dùng owner để lọc chính xác.
        if onlyLocal and owner and not ownerMatchesLocal(owner) then
            return
        end

        -- Nếu owner chưa có, nhưng root chính là plot của mình,
        -- vẫn chấp nhận vì cây nằm bên trong plot local.
        if onlyLocal and not owner then
            local plot = myPlot
            if plot and not obj:IsDescendantOf(plot) then
                return
            end
        end

        table.insert(out, {
            pos   = pos,
            name  = obj.Name,
            obj   = obj,
            owner = owner or lp.Name
        })
    end

    add(root)

    for _, obj in ipairs(root:GetDescendants()) do
        add(obj)
    end
end

local function refreshMyTrees(force)
    local now = os.clock()
    if not force and now - treeScanStamp < treeScanInterval then
        return myTrees
    end

    treeScanStamp = now
    myTrees = {}

    local plot = myPlot or findMyPlot()

    if plot then
        collectTrees(plot, myTrees, true)
    end

    -- Fallback rất chặt: chỉ tìm cây gần nhân vật khi game không
    -- expose plot rõ ràng. Vẫn phải có dấu hiệu owner/local plot.
    if #myTrees == 0 then
        local hrp = char and char:FindFirstChild("HumanoidRootPart")
        if hrp then
            for _, obj in ipairs(workspace:GetDescendants()) do
                if isTreeObject(obj) then
                    local owner = findOwnerInAncestors(obj)
                    local pos = getWorldPosition(obj)

                    if ownerMatchesLocal(owner) and pos
                        and (pos - hrp.Position).Magnitude <= 80 then
                        table.insert(myTrees, {
                            pos   = pos,
                            name  = obj.Name,
                            obj   = obj,
                            owner = lp.Name
                        })
                    end
                end
            end
        end
    end

    detectorArmed = (#myTrees > 0)
    return myTrees
end

-- ── LIGHTNING CLASSIFICATION ──────────────────────────────
local LIGHTNING_WORDS = {
    "lightning", "thunder", "thunderbolt",
    "lightningstrike", "thunderstrike",
    "bolt", "strike", "electricstrike",
    "zap", "shock", "lightningeffect"
}

local function hasLightningWord(name)
    local n = safeString(name)

    for _, word in ipairs(LIGHTNING_WORDS) do
        if n:find(word, 1, true) then
            return true
        end
    end

    return false
end

local function hasLightningAttribute(obj)
    if not obj then return false end

    local keys = {
        "Lightning", "IsLightning", "Thunder",
        "IsThunder", "LightningStrike", "IsStrike"
    }

    for _, key in ipairs(keys) do
        local ok, value = pcall(function()
            return obj:GetAttribute(key)
        end)

        if ok and value ~= nil then
            if value == true or tostring(value):lower() == "true" then
                return true
            end
        end
    end

    return false
end

local function lightningAncestor(obj)
    local cur = obj

    for _ = 1, 8 do
        if not cur then break end

        if hasLightningAttribute(cur) or hasLightningWord(cur.Name) then
            return cur
        end

        cur = cur.Parent
    end

    return nil
end

local function isLightningObject(obj)
    if not obj then return false end

    -- Ưu tiên tên/attribute rõ ràng.
    if hasLightningAttribute(obj) or hasLightningWord(obj.Name) then
        return true
    end

    -- Beam/Particle chỉ được coi là sét nếu nằm trong một
    -- ancestor có dấu hiệu lightning. Không còn rule "mọi Neon = sét".
    if obj:IsA("Beam") or obj:IsA("ParticleEmitter")
        or obj:IsA("Trail") then
        return lightningAncestor(obj) ~= nil
    end

    if obj:IsA("BasePart") then
        -- Part vàng/neon chỉ được nhận khi parent/ancestor có
        -- dấu hiệu sét; tránh false-positive từ map.
        if obj.Material == Enum.Material.Neon then
            return lightningAncestor(obj) ~= nil
        end
    end

    return false
end

-- ── FIND NEAREST TREE + OWNER ──────────────────────────────
local function getAllRelevantTrees()
    local trees = {}

    -- Khi detector đã ARMED, luôn ưu tiên cây local.
    for _, info in ipairs(refreshMyTrees(false)) do
        table.insert(trees, info)
    end

    -- Cây người khác: chỉ lấy cây thật sự có owner rõ ràng.
    -- Giới hạn theo bán kính quanh lightning effect để nhẹ máy.
    return trees
end

local function refreshAllTrees(force)
    local now = os.clock()
    if not force and now - allTreeScanStamp < allTreeScanInterval then
        return allTreesCache
    end

    allTreeScanStamp = now
    allTreesCache = {}

    -- Chỉ cache Model/BasePart có dấu hiệu là cây và owner xác định.
    -- Không giữ những object đã bị remove khỏi workspace.
    for _, obj in ipairs(workspace:GetDescendants()) do
        if isTreeObject(obj) then
            local owner = findOwnerInAncestors(obj)
            local pos = getWorldPosition(obj)

            if owner and pos then
                table.insert(allTreesCache, {
                    pos   = pos,
                    name  = obj.Name,
                    obj   = obj,
                    owner = owner
                })
            end
        end
    end

    return allTreesCache
end

local function findTreeNearLightning(lightPos)
    if not lightPos then return nil end

    local best, bestDist = nil, math.huge
    local maxDist = math.max(STATE.alertRadius, 30)

    -- 1) Local trees.
    for _, treeInfo in ipairs(myTrees) do
        if treeInfo.obj and treeInfo.obj.Parent then
            local pos = getWorldPosition(treeInfo.obj) or treeInfo.pos
            if pos then
                local d = (lightPos - pos).Magnitude
                if d < bestDist and d <= maxDist then
                    best = treeInfo
                    bestDist = d
                end
            end
        end
    end

    -- 2) Cây người khác từ cache owner-aware.
    for _, treeInfo in ipairs(refreshAllTrees(false)) do
        if treeInfo.obj and treeInfo.obj.Parent
            and not ownerMatchesLocal(treeInfo.owner) then

            local pos = getWorldPosition(treeInfo.obj) or treeInfo.pos
            if pos then
                local d = (lightPos - pos).Magnitude
                if d < bestDist and d <= maxDist then
                    best = treeInfo
                    bestDist = d
                end
            end
        end
    end

    return best, bestDist
end

-- ── NOTIFY/SOUND ───────────────────────────────────────────
local function playLightningSound()
    if not STATE.alertSound then return end

    pcall(function()
        local s = Instance.new("Sound")
        s.SoundId = "rbxassetid://9120386472"
        s.Volume  = 1
        s.Parent  = workspace
        s:Play()
        game:GetService("Debris"):AddItem(s, 5)
    end)
end

local function smartLightningAlert(treeInfo, dist, effect)
    if not treeInfo then return end

    local owner = treeInfo.owner or findOwnerInAncestors(treeInfo.obj)
    if not owner then
        owner = "Nguoi choi khac"
    end

    local isMine = ownerMatchesLocal(owner)
    if not isMine then
        -- Chỉ hiện tên người khác khi owner được xác định chắc chắn.
        local key = "OTHER|" .. safeString(owner) .. "|" ..
            tostring(treeInfo.obj) .. "|" .. tostring(effect)

        if alertCooldown[key] and os.clock() - alertCooldown[key] < 3 then
            return
        end
        alertCooldown[key] = os.clock()

        notify(
            "⚡  SÉT ĐÁNH CÂY NGƯỜI KHÁC",
            tostring(owner) .. "\nCây " .. tostring(treeInfo.name) ..
            " đang bị sét nhắm tới!\nKhoảng cách: " ..
            tostring(math.floor(dist or 0)) .. " studs",
            "lightning",
            5
        )
        return
    end

    local key = "MINE|" .. tostring(treeInfo.obj) .. "|" .. tostring(effect)

    if alertCooldown[key] and os.clock() - alertCooldown[key] < 3 then
        return
    end
    alertCooldown[key] = os.clock()

    task.spawn(function()
        flashAlert(lp.DisplayName, treeInfo.name)
    end)

    notify(
        "⚡  SÉT SẮP ĐÁNH CÂY CỦA BẠN",
        lp.DisplayName .. "\nCây " .. tostring(treeInfo.name) ..
        " đang bị sét nhắm tới!\nDự kiến trong " ..
        tostring(STATE.alertTime) .. " giây — hãy tránh khu vực!",
        "lightning",
        5
    )

    playLightningSound()
end

-- ── PROCESS ONE LIGHTNING EFFECT ───────────────────────────
local function processLightningObject(obj)
    if not STATE.lightningAlert or not detectorArmed then return end
    if not isLightningObject(obj) then return end

    local pos = getWorldPosition(obj)
    if not pos then
        local anc = lightningAncestor(obj)
        pos = getWorldPosition(anc)
    end
    if not pos then return end

    -- Fingerprint theo ancestor chính để một lightning effect có
    -- nhiều Part/Particle không tạo hàng loạt thông báo.
    local root = lightningAncestor(obj) or obj
    local fingerprint = tostring(root)

    if detectedKeys[fingerprint] then return end

    local treeInfo, dist = findTreeNearLightning(pos)
    if not treeInfo then return end

    detectedKeys[fingerprint] = true
    task.delay(3.5, function()
        detectedKeys[fingerprint] = nil
    end)

    smartLightningAlert(treeInfo, dist, fingerprint)
end

-- ── SMART DETECTOR LOOP ───────────────────────────────────
local function runDetector()
    while task.wait(0.20) do
        if not STATE.lightningAlert then
            detectorArmed = false
            continue
        end

        char = lp.Character or char
        if not char then
            detectorArmed = false
            continue
        end

        -- Đây là "arming gate": chưa trồng cây => không scan sét,
        -- không flash, không notification.
        refreshMyTrees(false)

        if not detectorArmed then
            continue
        end

        -- Cache cây có owner để có thể nhận diện cây người khác
        -- mà không quét toàn bộ workspace cho từng lightning effect.
        refreshAllTrees(false)

        -- Chỉ scan khi người chơi thực sự có cây.
        for _, obj in ipairs(workspace:GetDescendants()) do
            if isLightningObject(obj) then
                processLightningObject(obj)
            end
        end
    end
end

-- ── REAL-TIME HOOK ─────────────────────────────────────────
lightningConnection = workspace.DescendantAdded:Connect(function(obj)
    if not STATE.lightningAlert then return end

    -- Quan trọng: hook cũng không hoạt động trước khi có cây.
    refreshMyTrees(false)
    if not detectorArmed then return end

    task.delay(0.05, function()
        if obj and obj.Parent then
            processLightningObject(obj)
        end
    end)
end)

-- Khi bật lại detector, refresh ngay để tự ARM nếu đã trồng cây.
local function refreshLightningState()
    if STATE.lightningAlert then
        refreshMyTrees(true)
    else
        detectorArmed = false
    end
end

-- Start detector
task.spawn(runDetector)

-- ══════════════════════════════════════════════════════════
--  STARTUP NOTIFY (sau khi load xong)
-- ══════════════════════════════════════════════════════════
task.wait(3.2)  -- chờ loading screen xong

if SUPPORTED then
    notify("Greedy Farm Hub", "Chao " .. lp.DisplayName .. "! He thong set da san sang.", "success", 5)
    task.wait(1)
    notify("⚡ Doan Set", "Dang cho ban trong cay — detector se tu dong kich hoat khi phat hien cay cua ban.", "lightning", 5)
else
    notify("Khong ho tro",
        "PlaceId " .. tostring(game.PlaceId) .. " khong duoc ho tro.\nCan: " .. tostring(PLACE_ID),
        "error", 6)
end

print("[GreedyFarmHub] Loaded | PlaceId:", game.PlaceId, "| Supported:", SUPPORTED)
print("[GreedyFarmHub] Player:", lp.DisplayName, "| Lightning Detector: ACTIVE")
