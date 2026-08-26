--[[
    ╔══════════════════════════════════════════════════════════╗
    ║          DAYDREAMER HUB  —  by AnimeModHub              ║
    ║  Game 1 : 116456628154258  (Dungeon RPG / crystals)     ║
    ║  Game 2 : 117533937949084  (Phù Phép / lobby quest)     ║
    ╚══════════════════════════════════════════════════════════╝
    Features : auto farm · auto dodge · auto restart
               auto progress · auto run · auto cards
    Mobile-safe : no goto, no Lua-5.2 syntax
--]]

local Players          = game:GetService("Players")
local RunService       = game:GetService("RunService")
local TweenService     = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local lp  = Players.LocalPlayer
local pg  = lp.PlayerGui

-- ── PLACE DETECTION ───────────────────────────────────────
local SUPPORTED_PLACES = {
    [116456628154258] = "Dungeon RPG",
    [117533937949084] = "Phu Phep",
}
local currentPlaceId = game.PlaceId
local gameName       = SUPPORTED_PLACES[currentPlaceId]
local SUPPORTED      = gameName ~= nil

-- ── PALETTE ───────────────────────────────────────────────
local C = {
    bg      = Color3.fromRGB(10,  10,  16),
    panel   = Color3.fromRGB(18,  18,  28),
    card    = Color3.fromRGB(24,  24,  38),
    border  = Color3.fromRGB(48,  48,  72),
    accent  = Color3.fromRGB(138, 92,  246),
    accentL = Color3.fromRGB(167, 130, 255),
    accentD = Color3.fromRGB(91,  52,  190),
    off_    = Color3.fromRGB(55,  55,  75),
    text    = Color3.fromRGB(230, 230, 255),
    sub     = Color3.fromRGB(130, 130, 170),
    white   = Color3.fromRGB(255, 255, 255),
    green   = Color3.fromRGB(80,  220, 140),
    red     = Color3.fromRGB(240, 80,  80),
    yellow  = Color3.fromRGB(255, 210, 60),
}

-- ── STATE ─────────────────────────────────────────────────
local STATE = {
    autoFarm      = false,
    autoDodge     = false,
    autoRestart   = false,
    autoProgress  = false,
    autoRun       = false,
    autoCards     = false,
    hud           = true,
    autoLoad      = true,
    autoReconnect = true,
}

local activeTab   = "Combat"
local menuVisible = true
local dragging    = false
local dragStart, frameStart

-- ── TWEEN HELPER ──────────────────────────────────────────
local function tw(obj, props, t, style, dir)
    return TweenService:Create(
        obj,
        TweenInfo.new(t or 0.2,
            style or Enum.EasingStyle.Quart,
            dir   or Enum.EasingDirection.Out),
        props)
end

-- ══════════════════════════════════════════════════════════
--  CLEAN OLD GUI
-- ══════════════════════════════════════════════════════════
for _, g in ipairs(pg:GetChildren()) do
    if g.Name == "DaydreamerHub" or g.Name == "DHNotifGui" then g:Destroy() end
end

-- ══════════════════════════════════════════════════════════
--  NOTIFICATION GUI
-- ══════════════════════════════════════════════════════════
local notifGui = Instance.new("ScreenGui")
notifGui.Name           = "DHNotifGui"
notifGui.ResetOnSpawn   = false
notifGui.IgnoreGuiInset = true
notifGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
notifGui.Parent         = pg

local notifHolder = Instance.new("Frame")
notifHolder.Name              = "Holder"
notifHolder.Size              = UDim2.new(0, 300, 1, 0)
notifHolder.AnchorPoint       = Vector2.new(1, 1)
notifHolder.Position          = UDim2.new(1, -12, 1, -12)
notifHolder.BackgroundTransparency = 1
notifHolder.Parent            = notifGui

local notifList = Instance.new("UIListLayout")
notifList.SortOrder         = Enum.SortOrder.LayoutOrder
notifList.VerticalAlignment = Enum.VerticalAlignment.Bottom
notifList.Padding           = UDim.new(0, 6)
notifList.Parent            = notifHolder

local notifCount = 0
local function notify(title, body, kind)
    kind = kind or "info"
    local ic = (kind == "success" and C.green)
            or (kind == "warn"    and C.yellow)
            or (kind == "error"   and C.red)
            or C.accentL

    notifCount = notifCount + 1

    local card = Instance.new("Frame")
    card.Size              = UDim2.new(1, 0, 0, 60)
    card.BackgroundColor3  = C.panel
    card.BorderSizePixel   = 0
    card.LayoutOrder       = notifCount
    card.Parent            = notifHolder
    Instance.new("UICorner", card).CornerRadius = UDim.new(0, 10)

    local strip = Instance.new("Frame")
    strip.Size             = UDim2.new(0, 3, 1, 0)
    strip.BackgroundColor3 = ic
    strip.BorderSizePixel  = 0
    strip.Parent           = card
    Instance.new("UICorner", strip).CornerRadius = UDim.new(0, 2)

    local tl = Instance.new("TextLabel")
    tl.Size  = UDim2.new(1, -14, 0, 20)
    tl.Position = UDim2.new(0, 12, 0, 8)
    tl.BackgroundTransparency = 1
    tl.Text  = title
    tl.TextColor3 = C.white
    tl.TextSize = 12
    tl.Font  = Enum.Font.GothamBold
    tl.TextXAlignment = Enum.TextXAlignment.Left
    tl.Parent = card

    local bl = Instance.new("TextLabel")
    bl.Size  = UDim2.new(1, -14, 0, 24)
    bl.Position = UDim2.new(0, 12, 0, 30)
    bl.BackgroundTransparency = 1
    bl.Text  = body
    bl.TextColor3 = C.sub
    bl.TextSize = 10
    bl.Font  = Enum.Font.Gotham
    bl.TextXAlignment = Enum.TextXAlignment.Left
    bl.TextWrapped = true
    bl.Parent = card

    card.Position = UDim2.new(1, 10, 0, 0)
    tw(card, {Position = UDim2.new(0, 0, 0, 0)}, 0.28, Enum.EasingStyle.Back):Play()

    task.delay(4, function()
        if not card.Parent then return end
        tw(card, {BackgroundTransparency = 1}, 0.3):Play()
        tw(tl,   {TextTransparency = 1}, 0.3):Play()
        tw(bl,   {TextTransparency = 1}, 0.3):Play()
        tw(strip,{BackgroundTransparency = 1}, 0.3):Play()
        task.delay(0.35, function() pcall(function() card:Destroy() end) end)
    end)
end

-- ══════════════════════════════════════════════════════════
--  MAIN GUI
-- ══════════════════════════════════════════════════════════
local gui = Instance.new("ScreenGui")
gui.Name            = "DaydreamerHub"
gui.ResetOnSpawn    = false
gui.IgnoreGuiInset  = true
gui.ZIndexBehavior  = Enum.ZIndexBehavior.Sibling
gui.Parent          = pg

-- Root
local root = Instance.new("Frame")
root.Name              = "Root"
root.Size              = UDim2.new(0, 660, 0, 410)
root.AnchorPoint       = Vector2.new(0.5, 0.5)
root.Position          = UDim2.fromScale(0.5, 0.48)
root.BackgroundColor3  = C.bg
root.BorderSizePixel   = 0
root.Parent            = gui
Instance.new("UICorner", root).CornerRadius = UDim.new(0, 14)

local rootStroke = Instance.new("UIStroke")
rootStroke.Color       = C.accent
rootStroke.Thickness   = 1.2
rootStroke.Transparency = 0.5
rootStroke.Parent      = root

-- ── HEADER ────────────────────────────────────────────────
local header = Instance.new("Frame")
header.Size            = UDim2.new(1, 0, 0, 46)
header.BackgroundColor3 = C.panel
header.BorderSizePixel = 0
header.ZIndex          = 4
header.Parent          = root
Instance.new("UICorner", header).CornerRadius = UDim.new(0, 14)

local hFix = Instance.new("Frame")
hFix.Size              = UDim2.new(1, 0, 0, 14)
hFix.Position          = UDim2.new(0, 0, 1, -14)
hFix.BackgroundColor3  = C.panel
hFix.BorderSizePixel   = 0
hFix.ZIndex            = 3
hFix.Parent            = header

-- Pulse dot
local dot = Instance.new("Frame")
dot.Size               = UDim2.new(0, 8, 0, 8)
dot.Position           = UDim2.new(0, 16, 0.5, -4)
dot.BackgroundColor3   = C.accent
dot.BorderSizePixel    = 0
dot.ZIndex             = 5
dot.Parent             = header
Instance.new("UICorner", dot).CornerRadius = UDim.new(1, 0)

local titleLbl = Instance.new("TextLabel")
titleLbl.Size              = UDim2.new(0, 120, 1, 0)
titleLbl.Position          = UDim2.new(0, 30, 0, 0)
titleLbl.BackgroundTransparency = 1
titleLbl.Text              = "daydreamer"
titleLbl.TextColor3        = C.text
titleLbl.TextSize          = 13
titleLbl.Font              = Enum.Font.GothamBold
titleLbl.TextXAlignment    = Enum.TextXAlignment.Left
titleLbl.ZIndex            = 5
titleLbl.Parent            = header

-- Game badge
local badge = Instance.new("Frame")
badge.Size                 = UDim2.new(0, 176, 0, 24)
badge.AnchorPoint          = Vector2.new(0.5, 0.5)
badge.Position             = UDim2.new(0.5, 0, 0.5, 0)
badge.BackgroundColor3     = SUPPORTED and C.accentD or Color3.fromRGB(70, 15, 15)
badge.BorderSizePixel      = 0
badge.ZIndex               = 5
badge.Parent               = header
Instance.new("UICorner", badge).CornerRadius = UDim.new(0, 6)

local badgeTxt = Instance.new("TextLabel")
badgeTxt.Size              = UDim2.fromScale(1, 1)
badgeTxt.BackgroundTransparency = 1
badgeTxt.Text              = SUPPORTED and ("● " .. gameName) or "● Khong ho tro"
badgeTxt.TextColor3        = SUPPORTED and C.accentL or C.red
badgeTxt.TextSize          = 11
badgeTxt.Font              = Enum.Font.GothamBold
badgeTxt.ZIndex            = 6
badgeTxt.Parent            = badge

-- Minimize
local minBtn = Instance.new("TextButton")
minBtn.Size                = UDim2.new(0, 26, 0, 26)
minBtn.AnchorPoint         = Vector2.new(1, 0.5)
minBtn.Position            = UDim2.new(1, -44, 0.5, 0)
minBtn.BackgroundColor3    = Color3.fromRGB(48, 40, 8)
minBtn.BorderSizePixel     = 0
minBtn.Text                = "-"
minBtn.TextColor3          = C.yellow
minBtn.TextSize            = 14
minBtn.Font                = Enum.Font.GothamBold
minBtn.AutoButtonColor     = false
minBtn.ZIndex              = 6
minBtn.Parent              = header
Instance.new("UICorner", minBtn).CornerRadius = UDim.new(0, 6)

-- Close
local closeBtn = Instance.new("TextButton")
closeBtn.Size              = UDim2.new(0, 26, 0, 26)
closeBtn.AnchorPoint       = Vector2.new(1, 0.5)
closeBtn.Position          = UDim2.new(1, -12, 0.5, 0)
closeBtn.BackgroundColor3  = Color3.fromRGB(58, 18, 18)
closeBtn.BorderSizePixel   = 0
closeBtn.Text              = "x"
closeBtn.TextColor3        = C.red
closeBtn.TextSize          = 13
closeBtn.Font              = Enum.Font.GothamBold
closeBtn.AutoButtonColor   = false
closeBtn.ZIndex            = 6
closeBtn.Parent            = header
Instance.new("UICorner", closeBtn).CornerRadius = UDim.new(0, 6)

-- ── TAB BAR ───────────────────────────────────────────────
local tabBar = Instance.new("Frame")
tabBar.Size              = UDim2.new(1, -24, 0, 36)
tabBar.Position          = UDim2.new(0, 12, 0, 54)
tabBar.BackgroundColor3  = C.panel
tabBar.BorderSizePixel   = 0
tabBar.ZIndex            = 4
tabBar.Parent            = root
Instance.new("UICorner", tabBar).CornerRadius = UDim.new(0, 10)

local tabLL = Instance.new("UIListLayout")
tabLL.FillDirection      = Enum.FillDirection.Horizontal
tabLL.VerticalAlignment  = Enum.VerticalAlignment.Center
tabLL.HorizontalAlignment= Enum.HorizontalAlignment.Center
tabLL.Padding            = UDim.new(0, 4)
tabLL.Parent             = tabBar

local tabPad = Instance.new("UIPadding")
tabPad.PaddingLeft       = UDim.new(0, 6)
tabPad.PaddingRight      = UDim.new(0, 6)
tabPad.Parent            = tabBar

-- ── CONTENT AREA ──────────────────────────────────────────
local content = Instance.new("Frame")
content.Size             = UDim2.new(1, -24, 1, -106)
content.Position         = UDim2.new(0, 12, 0, 98)
content.BackgroundTransparency = 1
content.ClipsDescendants = true
content.ZIndex           = 3
content.Parent           = root

-- ── FOOTER ────────────────────────────────────────────────
local footer = Instance.new("TextLabel")
footer.Size              = UDim2.new(1, -24, 0, 18)
footer.AnchorPoint       = Vector2.new(0, 1)
footer.Position          = UDim2.new(0, 12, 1, -3)
footer.BackgroundTransparency = 1
footer.Text              = "discord.gg/daydreamer    production on delta"
footer.TextColor3        = C.sub
footer.TextSize          = 9
footer.Font              = Enum.Font.Code
footer.TextXAlignment    = Enum.TextXAlignment.Left
footer.ZIndex            = 2
footer.Parent            = root

-- ══════════════════════════════════════════════════════════
--  DRAG
-- ══════════════════════════════════════════════════════════
header.InputBegan:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging   = true
        dragStart  = inp.Position
        frameStart = root.Position
    end
end)
UserInputService.InputChanged:Connect(function(inp)
    if dragging then
        if inp.UserInputType == Enum.UserInputType.Touch
        or inp.UserInputType == Enum.UserInputType.MouseMovement then
            local d = inp.Position - dragStart
            root.Position = UDim2.new(
                frameStart.X.Scale, frameStart.X.Offset + d.X,
                frameStart.Y.Scale, frameStart.Y.Offset + d.Y)
        end
    end
end)
UserInputService.InputEnded:Connect(function(inp)
    if inp.UserInputType == Enum.UserInputType.Touch
    or inp.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging = false
    end
end)

-- ══════════════════════════════════════════════════════════
--  CLOSE / MINIMIZE
-- ══════════════════════════════════════════════════════════
closeBtn.MouseButton1Click:Connect(function()
    tw(root, {Size = UDim2.new(0,0,0,0)}, 0.22, Enum.EasingStyle.Back, Enum.EasingDirection.In):Play()
    task.delay(0.25, function()
        pcall(function() gui:Destroy() end)
        pcall(function() notifGui:Destroy() end)
    end)
end)

minBtn.MouseButton1Click:Connect(function()
    menuVisible = not menuVisible
    local sz = menuVisible and UDim2.new(0,660,0,410) or UDim2.new(0,660,0,48)
    tw(root, {Size = sz}, 0.28, Enum.EasingStyle.Quart):Play()
    task.delay(0.05, function()
        content.Visible = menuVisible
        tabBar.Visible  = menuVisible
        footer.Visible  = menuVisible
    end)
end)

-- ══════════════════════════════════════════════════════════
--  TOGGLE FACTORY
-- ══════════════════════════════════════════════════════════
local function makeToggle(parent, labelText, descText, stateKey)
    local card = Instance.new("Frame")
    card.Size             = UDim2.new(0.47, 0, 0, 72)
    card.BackgroundColor3 = C.card
    card.BorderSizePixel  = 0
    card.ZIndex           = 5
    card.Parent           = parent
    Instance.new("UICorner", card).CornerRadius = UDim.new(0, 10)

    local stroke = Instance.new("UIStroke")
    stroke.Color       = C.border
    stroke.Thickness   = 1
    stroke.Transparency= 0.4
    stroke.Parent      = card

    local lbl = Instance.new("TextLabel")
    lbl.Size             = UDim2.new(1, -56, 0, 20)
    lbl.Position         = UDim2.new(0, 12, 0, 10)
    lbl.BackgroundTransparency = 1
    lbl.Text             = labelText
    lbl.TextColor3       = C.text
    lbl.TextSize         = 13
    lbl.Font             = Enum.Font.GothamBold
    lbl.TextXAlignment   = Enum.TextXAlignment.Left
    lbl.ZIndex           = 6
    lbl.Parent           = card

    local desc = Instance.new("TextLabel")
    desc.Size            = UDim2.new(1, -56, 0, 28)
    desc.Position        = UDim2.new(0, 12, 0, 34)
    desc.BackgroundTransparency = 1
    desc.Text            = "+ " .. descText
    desc.TextColor3      = C.sub
    desc.TextSize        = 10
    desc.Font            = Enum.Font.Gotham
    desc.TextXAlignment  = Enum.TextXAlignment.Left
    desc.TextWrapped     = true
    desc.ZIndex          = 6
    desc.Parent          = card

    -- Track
    local track = Instance.new("Frame")
    track.Size            = UDim2.new(0, 42, 0, 22)
    track.AnchorPoint     = Vector2.new(1, 0.5)
    track.Position        = UDim2.new(1, -12, 0.5, 0)
    track.BackgroundColor3= STATE[stateKey] and C.accent or C.off_
    track.BorderSizePixel = 0
    track.ZIndex          = 6
    track.Parent          = card
    Instance.new("UICorner", track).CornerRadius = UDim.new(1, 0)

    -- Thumb
    local thumb = Instance.new("Frame")
    thumb.Size            = UDim2.new(0, 16, 0, 16)
    thumb.AnchorPoint     = Vector2.new(0, 0.5)
    thumb.Position        = STATE[stateKey]
        and UDim2.new(0, 23, 0.5, 0) or UDim2.new(0, 3, 0.5, 0)
    thumb.BackgroundColor3= C.white
    thumb.BorderSizePixel = 0
    thumb.ZIndex          = 7
    thumb.Parent          = track
    Instance.new("UICorner", thumb).CornerRadius = UDim.new(1, 0)

    local btn = Instance.new("TextButton")
    btn.Size             = UDim2.fromScale(1, 1)
    btn.BackgroundTransparency = 1
    btn.Text             = ""
    btn.ZIndex           = 8
    btn.AutoButtonColor  = false
    btn.Parent           = card

    btn.MouseButton1Click:Connect(function()
        if not SUPPORTED then
            notify("Khong ho tro", "Game nay chua duoc ho tro.", "error")
            return
        end
        STATE[stateKey] = not STATE[stateKey]
        local on = STATE[stateKey]
        tw(track, {BackgroundColor3 = on and C.accent or C.off_}, 0.16):Play()
        tw(thumb, {Position = on and UDim2.new(0,23,0.5,0) or UDim2.new(0,3,0.5,0)},
           0.16, Enum.EasingStyle.Back):Play()
        tw(stroke, {
            Color       = on and C.accent or C.border,
            Transparency= on and 0.1 or 0.4
        }, 0.18):Play()
        notify(
            on and ("Bat: " .. labelText) or ("Tat: " .. labelText),
            on and "Da bat" or "Da tat",
            on and "success" or "info"
        )
    end)

    btn.MouseEnter:Connect(function()
        tw(card, {BackgroundColor3 = Color3.fromRGB(30,30,48)}, 0.1):Play()
    end)
    btn.MouseLeave:Connect(function()
        tw(card, {BackgroundColor3 = C.card}, 0.1):Play()
    end)

    return card
end

-- ══════════════════════════════════════════════════════════
--  TAB PAGES
-- ══════════════════════════════════════════════════════════
local pages   = {}
local tabBtns = {}
local TABS    = {"Configs","Interface","Combat","Runs","Gear"}

for _, tname in ipairs(TABS) do
    local btn = Instance.new("TextButton")
    btn.Size             = UDim2.new(0, 100, 0, 28)
    btn.BackgroundColor3 = (tname == activeTab) and C.accent or Color3.fromRGB(28,28,44)
    btn.BorderSizePixel  = 0
    btn.Text             = tname
    btn.TextColor3       = (tname == activeTab) and C.white or C.sub
    btn.TextSize         = 12
    btn.Font             = Enum.Font.GothamBold
    btn.AutoButtonColor  = false
    btn.ZIndex           = 5
    btn.Parent           = tabBar
    Instance.new("UICorner", btn).CornerRadius = UDim.new(0, 7)
    tabBtns[tname] = btn

    local page = Instance.new("Frame")
    page.Size  = UDim2.fromScale(1, 1)
    page.BackgroundTransparency = 1
    page.Visible = (tname == activeTab)
    page.ZIndex  = 4
    page.Parent  = content
    pages[tname] = page
end

local function switchTab(tname)
    if tname == activeTab then return end
    pages[activeTab].Visible = false
    tw(tabBtns[activeTab], {BackgroundColor3 = Color3.fromRGB(28,28,44), TextColor3 = C.sub}, 0.14):Play()
    activeTab = tname
    pages[tname].Visible = true
    tw(tabBtns[tname], {BackgroundColor3 = C.accent, TextColor3 = C.white}, 0.14):Play()
end

for _, tname in ipairs(TABS) do
    tabBtns[tname].MouseButton1Click:Connect(function() switchTab(tname) end)
end

-- ══════════════════════════════════════════════════════════
--  PAGE BUILDER HELPER (grid of toggles)
-- ══════════════════════════════════════════════════════════
local function buildGrid(pageName)
    local fr = Instance.new("Frame")
    fr.Size  = UDim2.fromScale(1, 1)
    fr.BackgroundTransparency = 1
    fr.Parent = pages[pageName]

    local gl = Instance.new("UIGridLayout")
    gl.CellSize              = UDim2.new(0.47, 0, 0, 72)
    gl.CellPaddingX          = UDim.new(0.04, 0)
    gl.CellPaddingY          = UDim.new(0, 8)
    gl.HorizontalAlignment   = Enum.HorizontalAlignment.Center
    gl.VerticalAlignment     = Enum.VerticalAlignment.Top
    gl.SortOrder             = Enum.SortOrder.LayoutOrder
    gl.Parent                = fr

    local gpad = Instance.new("UIPadding")
    gpad.PaddingTop = UDim.new(0, 8)
    gpad.Parent     = fr

    return fr
end

-- PAGE: COMBAT
do
    local g = buildGrid("Combat")
    local t = {
        {"auto farm",     "auto-attack the highest-health enemy", "autoFarm"},
        {"auto dodge",    "relocate out of attack telegraphs",    "autoDodge"},
        {"auto restart",  "refill health + restart on death",     "autoRestart"},
        {"auto progress", "advance rooms/waves when cleared",     "autoProgress"},
    }
    for i, v in ipairs(t) do
        local c = makeToggle(g, v[1], v[2], v[3])
        c.LayoutOrder = i
    end
end

-- PAGE: RUNS
do
    local g = buildGrid("Runs")
    local t = {
        {"auto run",   "join the chosen world from the lobby", "autoRun"},
        {"auto cards", "automatically choose the strongest card", "autoCards"},
    }
    for i, v in ipairs(t) do
        local c = makeToggle(g, v[1], v[2], v[3])
        c.LayoutOrder = i
    end
end

-- PAGE: INTERFACE
do
    local g = buildGrid("Interface")
    local t = {
        {"HUD",            "random hud stuff",                       "hud"},
        {"Auto Load",      "load daydreamer automatically after tp", "autoLoad"},
        {"Auto Reconnect", "auto rejoins after disconnects",         "autoReconnect"},
    }
    for i, v in ipairs(t) do
        local c = makeToggle(g, v[1], v[2], v[3])
        c.LayoutOrder = i
    end
end

-- PAGE: CONFIGS (info table)
do
    local scroll = Instance.new("ScrollingFrame")
    scroll.Size               = UDim2.fromScale(1, 1)
    scroll.BackgroundTransparency = 1
    scroll.BorderSizePixel    = 0
    scroll.ScrollBarThickness = 3
    scroll.ScrollBarImageColor3 = C.accent
    scroll.CanvasSize         = UDim2.new(0, 0, 0, 260)
    scroll.Parent             = pages["Configs"]

    local spad = Instance.new("UIPadding")
    spad.PaddingTop  = UDim.new(0, 8)
    spad.PaddingLeft = UDim.new(0, 4)
    spad.Parent      = scroll

    local sl = Instance.new("UIListLayout")
    sl.Padding    = UDim.new(0, 6)
    sl.SortOrder  = Enum.SortOrder.LayoutOrder
    sl.Parent     = scroll

    local rows = {
        {"Game",     SUPPORTED and gameName or "Khong ho tro", SUPPORTED and C.green or C.red},
        {"Place ID", tostring(currentPlaceId),                  C.accentL},
        {"Player",   lp.DisplayName,                            C.text},
        {"Version",  "v1.0.0",                                  C.yellow},
    }
    for _, r in ipairs(rows) do
        local row = Instance.new("Frame")
        row.Size              = UDim2.new(1, -8, 0, 34)
        row.BackgroundColor3  = C.card
        row.BorderSizePixel   = 0
        row.Parent            = scroll
        Instance.new("UICorner", row).CornerRadius = UDim.new(0, 8)

        local kl = Instance.new("TextLabel")
        kl.Size  = UDim2.new(0.45, 0, 1, 0)
        kl.Position = UDim2.new(0, 12, 0, 0)
        kl.BackgroundTransparency = 1
        kl.Text  = r[1]
        kl.TextColor3 = C.sub
        kl.TextSize = 11
        kl.Font  = Enum.Font.Gotham
        kl.TextXAlignment = Enum.TextXAlignment.Left
        kl.ZIndex = 5
        kl.Parent = row

        local vl = Instance.new("TextLabel")
        vl.Size  = UDim2.new(0.5, -8, 1, 0)
        vl.AnchorPoint = Vector2.new(1, 0)
        vl.Position = UDim2.new(1, -8, 0, 0)
        vl.BackgroundTransparency = 1
        vl.Text  = r[2]
        vl.TextColor3 = r[3]
        vl.TextSize = 11
        vl.Font  = Enum.Font.GothamBold
        vl.TextXAlignment = Enum.TextXAlignment.Right
        vl.ZIndex = 5
        vl.Parent = row
    end
end

-- PAGE: GEAR
do
    local lbl = Instance.new("TextLabel")
    lbl.Size  = UDim2.fromScale(1, 1)
    lbl.BackgroundTransparency = 1
    lbl.Text  = "Gear config\nComing soon..."
    lbl.TextColor3 = C.sub
    lbl.TextSize = 13
    lbl.Font  = Enum.Font.GothamBold
    lbl.Parent = pages["Gear"]
end

-- ══════════════════════════════════════════════════════════
--  OPEN ANIMATION + PULSE DOT
-- ══════════════════════════════════════════════════════════
root.Size = UDim2.new(0, 0, 0, 0)
tw(root, {Size = UDim2.new(0,660,0,410)}, 0.32, Enum.EasingStyle.Back, Enum.EasingDirection.Out):Play()

task.spawn(function()
    while gui and gui.Parent do
        tw(dot, {BackgroundTransparency = 0.7}, 0.9, Enum.EasingStyle.Sine):Play()
        task.wait(1)
        tw(dot, {BackgroundTransparency = 0}, 0.9, Enum.EasingStyle.Sine):Play()
        task.wait(1)
    end
end)

-- ══════════════════════════════════════════════════════════
--  STARTUP NOTIFY
-- ══════════════════════════════════════════════════════════
task.wait(0.5)
if SUPPORTED then
    notify("Daydreamer Hub", "Game ho tro: " .. gameName, "success")
else
    notify("Khong ho tro", "PlaceId " .. tostring(currentPlaceId), "error")
    notify("Game duoc ho tro", "116456628154258 / 117533937949084", "info")
end

-- ══════════════════════════════════════════════════════════
--  GAME LOOPS
-- ══════════════════════════════════════════════════════════
if SUPPORTED then

-- AUTO FARM
task.spawn(function()
    while task.wait(0.12) do
        if not STATE.autoFarm then continue end
        local char = lp.Character
        if not char then continue end
        local hrp = char:FindFirstChild("HumanoidRootPart")
        local hum = char:FindFirstChildOfClass("Humanoid")
        if not hrp or not hum or hum.Health <= 0 then continue end

        local bestTarget, bestHp = nil, -1
        for _, obj in ipairs(workspace:GetDescendants()) do
            local h = obj:FindFirstChildOfClass("Humanoid")
            if h and h.Health > 0 and obj ~= char then
                local isPlayer = false
                for _, pl in ipairs(Players:GetPlayers()) do
                    if pl.Character == obj then isPlayer = true break end
                end
                if not isPlayer and h.Health > bestHp then
                    bestHp     = h.Health
                    bestTarget = obj
                end
            end
        end

        if bestTarget then
            local tr = bestTarget:FindFirstChild("HumanoidRootPart")
            if tr then
                local dist = (hrp.Position - tr.Position).Magnitude
                if dist > 8 then
                    hum:MoveTo(tr.Position)
                else
                    local tool = lp.Backpack:FindFirstChildOfClass("Tool")
                             or char:FindFirstChildOfClass("Tool")
                    if tool then
                        local re = tool:FindFirstChild("RemoteEvent")
                        if re then pcall(function() re:FireServer() end) end
                    end
                end
            end
        end
    end
end)

-- AUTO DODGE
task.spawn(function()
    while task.wait(0.06) do
        if not STATE.autoDodge then continue end
        local char = lp.Character
        if not char then continue end
        local hrp = char:FindFirstChild("HumanoidRootPart")
        local hum = char:FindFirstChildOfClass("Humanoid")
        if not hrp or not hum or hum.Health <= 0 then continue end

        local safeDir = Vector3.new(0,0,0)
        local inDanger = false
        for _, obj in ipairs(workspace:GetDescendants()) do
            if obj:IsA("BasePart") then
                local n = obj.Name:lower()
                if n:find("aoe") or n:find("danger") or n:find("telegraph")
                or n:find("damage") or n:find("zone") then
                    local d = (hrp.Position - obj.Position).Magnitude
                    if d < 12 then
                        inDanger = true
                        safeDir  = safeDir + (hrp.Position - obj.Position).Unit
                    end
                end
            end
        end
        if inDanger and safeDir.Magnitude > 0 then
            hum:MoveTo(hrp.Position + safeDir.Unit * 14)
        end
    end
end)

-- AUTO RESTART
task.spawn(function()
    while task.wait(1) do
        if not STATE.autoRestart then continue end
        local char = lp.Character
        if not char then continue end
        local hum = char:FindFirstChildOfClass("Humanoid")
        if not hum then continue end
        if hum.Health <= 0 then
            task.wait(2.5)
            local rs = game:GetService("ReplicatedStorage")
            for _, rname in ipairs({"Respawn","Restart","RestartRun","RespawnPlayer","Revive"}) do
                pcall(function()
                    local r = rs:FindFirstChild(rname, true)
                    if r and r:IsA("RemoteEvent") then r:FireServer() end
                end)
            end
            pcall(function() lp:LoadCharacter() end)
        end
    end
end)

-- AUTO PROGRESS
task.spawn(function()
    while task.wait(2) do
        if not STATE.autoProgress then continue end
        local rs = game:GetService("ReplicatedStorage")
        for _, n in ipairs({"NextRoom","NextWave","AdvanceRoom","AdvanceWave","RoomCleared","WaveCleared","Progress"}) do
            pcall(function()
                local r = rs:FindFirstChild(n, true)
                if r and r:IsA("RemoteEvent") then r:FireServer() end
            end)
        end
    end
end)

-- AUTO RUN
task.spawn(function()
    while task.wait(3) do
        if not STATE.autoRun then continue end
        local rs = game:GetService("ReplicatedStorage")
        for _, n in ipairs({"JoinRun","StartRun","EnterDungeon","JoinWorld","AutoJoin"}) do
            pcall(function()
                local r = rs:FindFirstChild(n, true)
                if r and r:IsA("RemoteEvent") then r:FireServer() end
            end)
        end
    end
end)

-- AUTO CARDS
task.spawn(function()
    while task.wait(0.5) do
        if not STATE.autoCards then continue end
        local rs = game:GetService("ReplicatedStorage")
        for _, n in ipairs({"SelectCard","ChooseCard","PickCard","CardSelect"}) do
            pcall(function()
                local r = rs:FindFirstChild(n, true)
                if r and r:IsA("RemoteEvent") then r:FireServer(1) end
            end)
        end
    end
end)

end -- if SUPPORTED

print("[DaydreamerHub] Loaded | PlaceId:", currentPlaceId, "| Supported:", SUPPORTED)
