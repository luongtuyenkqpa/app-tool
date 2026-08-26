--[[
    ╔══════════════════════════════════════════════════════════════╗
    ║   SÂN ĐẤU SINH TỬ — Menu Chiến Đấu v6.0                    ║
    ║   Game: [BATTLEPASS ⭐] Sân đấu sinh tử                     ║
    ║   PlaceId: 100484168444874                                   ║
    ║   v6.0: Auto Né v6 | Tăng ST x3 | Scan Vũ Khí Địch         ║
    ║         Né thông minh + x3 damage + info vũ khí             ║
    ╚══════════════════════════════════════════════════════════════╝
--]]

--==================================================
-- KIỂM TRA GAME HỖ TRỢ
--==================================================
local SUPPORTED_PLACE_IDS = {
    [100484168444874] = true,
    [4810740296]      = true,
}

local currentPlaceId = game.PlaceId
local isSupported    = SUPPORTED_PLACE_IDS[currentPlaceId] or false

--==================================================
-- SERVICES
--==================================================
local Players          = game:GetService("Players")
local RunService       = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local TweenService     = game:GetService("TweenService")
local Debris           = game:GetService("Debris")

local LocalPlayer = Players.LocalPlayer
local Camera      = workspace.CurrentCamera

--==================================================
-- STATE CHÍNH
--==================================================
local STATE = {
    autoNe          = false,
    damageBoost     = false,
    weaponScan      = false,
    boostLevel      = 30,
}

--==================================================
-- THÔNG BÁO NOTIFICATION (giữ nguyên)
--==================================================
local function showNotif(title, msg, color, duration)
    duration = duration or 3
    local gui = LocalPlayer:FindFirstChild("PlayerGui")
    if not gui then return end

    local sGui = Instance.new("ScreenGui")
    sGui.Name         = "SDST_Notif_" .. tostring(tick())
    sGui.ResetOnSpawn = false
    sGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    sGui.IgnoreGuiInset = true
    sGui.Parent       = gui

    local W, H = 340, 70
    local frame = Instance.new("Frame", sGui)
    frame.Size             = UDim2.fromOffset(W, H)
    frame.Position         = UDim2.new(1, W + 10, 0, 80)
    frame.BackgroundColor3 = Color3.fromRGB(12, 12, 22)
    frame.BorderSizePixel  = 0
    frame.AnchorPoint      = Vector2.new(0, 0)
    Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 12)
    local stroke = Instance.new("UIStroke", frame)
    stroke.Color     = color or Color3.fromRGB(200, 60, 60)
    stroke.Thickness = 2

    local bar = Instance.new("Frame", frame)
    bar.Size             = UDim2.fromOffset(5, H)
    bar.BackgroundColor3 = color or Color3.fromRGB(200, 60, 60)
    bar.BorderSizePixel  = 0
    Instance.new("UICorner", bar).CornerRadius = UDim.new(0, 3)

    local tLbl = Instance.new("TextLabel", frame)
    tLbl.Size             = UDim2.new(1, -20, 0, 22)
    tLbl.Position         = UDim2.fromOffset(16, 8)
    tLbl.BackgroundTransparency = 1
    tLbl.Text             = title
    tLbl.TextColor3       = color or Color3.fromRGB(255, 100, 100)
    tLbl.TextSize         = 13
    tLbl.Font             = Enum.Font.GothamBold
    tLbl.TextXAlignment   = Enum.TextXAlignment.Left

    local mLbl = Instance.new("TextLabel", frame)
    mLbl.Size             = UDim2.new(1, -20, 0, 30)
    mLbl.Position         = UDim2.fromOffset(16, 32)
    mLbl.BackgroundTransparency = 1
    mLbl.Text             = msg
    mLbl.TextColor3       = Color3.fromRGB(200, 200, 210)
    mLbl.TextSize         = 11
    mLbl.Font             = Enum.Font.Gotham
    mLbl.TextXAlignment   = Enum.TextXAlignment.Left
    mLbl.TextWrapped      = true

    TweenService:Create(frame, TweenInfo.new(0.35, Enum.EasingStyle.Quart, Enum.EasingDirection.Out), {
        Position = UDim2.new(1, -(W + 14), 0, 80)
    }):Play()

    task.delay(duration, function()
        TweenService:Create(frame, TweenInfo.new(0.3, Enum.EasingStyle.Quart, Enum.EasingDirection.In), {
            Position = UDim2.new(1, W + 10, 0, 80)
        }):Play()
        task.wait(0.35)
        sGui:Destroy()
    end)
end

--==================================================
-- KHỞI ĐỘNG — KIỂM TRA GAME
--==================================================
task.wait(1.5)

if isSupported then
    showNotif(
        "✅ Script khởi động thành công!",
        "Game: Sân đấu sinh tử đã được nhận diện.\nMenu sẵn sàng hoạt động!",
        Color3.fromRGB(50, 220, 100), 5
    )
    print("[SDST v6.0] ✅ Script tải thành công! PlaceId: " .. currentPlaceId)
else
    showNotif(
        "⚠️  Game không được hỗ trợ đầy đủ!",
        "PlaceId: " .. tostring(currentPlaceId) .. "\nMột số chức năng có thể không hoạt động.",
        Color3.fromRGB(255, 160, 30), 6
    )
    print("[SDST v6.0] ⚠️  PlaceId không khớp: " .. tostring(currentPlaceId))
end


--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 1: AUTO NÉ v6 — WEAPON HITBOX DETECTION
-- ████████████████████████████████████████████████
-- Kỹ thuật v6:
--   ✅ Hook BasePart.Touched trên TẤT CẢ parts của địch
--      (kể cả tool/weapon được equip trong tay)
--   ✅ Khi bất kỳ part nào của địch CHẠM vào CHARACTER mình
--      → Xác định đây là đòn chém → Teleport NGAY khỏi điểm chém
--   ✅ Teleport instant CFrame + AlignPosition giữ vị trí
--   ✅ Proximity guard: địch vào trong 4.5 studs → né sẵn
--   ✅ HP-drop fallback: nếu bỏ lỡ touched event → né sau
--==================================================
local neConns        = {}
local autoNeHbConn   = nil
local neTouchConns   = {}
local lastDodgeTime  = 0
local DODGE_COOLDOWN = 0.4
local neTrackedHP    = 0
local dodgeActive    = false
local neAlignPos     = nil
local neAtt0         = nil
local neAnchor       = nil

local function getMyChar()
    local char = LocalPlayer.Character
    if not char then return nil, nil, nil end
    local root = char:FindFirstChild("HumanoidRootPart")
    local hum  = char:FindFirstChildOfClass("Humanoid")
    return char, root, hum
end

local function findNearestEnemy()
    local _, myRoot, _ = getMyChar()
    if not myRoot then return nil, math.huge end
    local best, bestDist = nil, math.huge
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer and p.Character then
            local eRoot = p.Character:FindFirstChild("HumanoidRootPart")
            local eHum  = p.Character:FindFirstChildOfClass("Humanoid")
            if eRoot and eHum and eHum.Health > 0 then
                local d = (eRoot.Position - myRoot.Position).Magnitude
                if d < bestDist then bestDist = d; best = eRoot end
            end
        end
    end
    return best, bestDist
end

local function cleanAlignPos()
    if neAlignPos then pcall(function() neAlignPos:Destroy() end); neAlignPos = nil end
    if neAtt0     then pcall(function() neAtt0:Destroy()    end); neAtt0     = nil end
    if neAnchor   then pcall(function() neAnchor:Destroy()  end); neAnchor   = nil end
end

-- Core dodge: teleport ngay khỏi điểm bị chém
-- hitOrigin = vị trí của weapon part vừa chạm (nơi đòn chém xuất phát)
local function doDodge(hitOrigin)
    local now = tick()
    if now - lastDodgeTime < DODGE_COOLDOWN then return end
    if dodgeActive then return end
    lastDodgeTime = now
    dodgeActive   = true

    local char, myRoot, myHum = getMyChar()
    if not myRoot or not myHum or myHum.Health <= 0 then
        dodgeActive = false; return
    end

    -- Tính hướng né: NGƯỢC chiều đòn chém (thoát khỏi điểm chém)
    local dodgeDir
    if hitOrigin then
        -- Né theo hướng ngược lại từ điểm chém đến mình
        local awayFromHit = myRoot.Position - hitOrigin
        awayFromHit = Vector3.new(awayFromHit.X, 0, awayFromHit.Z)
        if awayFromHit.Magnitude > 0.01 then
            awayFromHit = awayFromHit.Unit
        else
            awayFromHit = myRoot.CFrame.LookVector
        end
        -- Kết hợp: 70% ra sau đòn chém + 30% sang bên để tránh follow-up
        local side  = awayFromHit:Cross(Vector3.new(0, 1, 0)).Unit
        local sign  = (math.random(0, 1) == 0) and 1 or -1
        dodgeDir    = (awayFromHit * 0.7 + side * sign * 0.3).Unit
    else
        -- Fallback: né sang bên + ra sau
        local look  = myRoot.CFrame.LookVector
        local right = myRoot.CFrame.RightVector
        local sign  = (math.random(0, 1) == 0) and 1 or -1
        dodgeDir    = (right * sign * 0.5 - look * 0.5).Unit
        dodgeDir    = Vector3.new(dodgeDir.X, 0, dodgeDir.Z).Unit
    end

    local DODGE_DIST = 18  -- studs
    local targetPos  = myRoot.Position + dodgeDir * DODGE_DIST + Vector3.new(0, 0.05, 0)

    -- ✅ Instant CFrame teleport (LocalPlayer owns character)
    pcall(function()
        cleanAlignPos()
        myRoot.CFrame = CFrame.new(targetPos) * (myRoot.CFrame - myRoot.CFrame.p)
    end)

    -- ✅ AlignPosition: giữ vị trí 0.35s, không bị kéo lại bởi physics
    pcall(function()
        local att0   = Instance.new("Attachment"); att0.Parent = myRoot
        local anchor = Instance.new("Part")
        anchor.Anchored     = true
        anchor.CanCollide   = false
        anchor.Transparency = 1
        anchor.Size         = Vector3.new(1, 1, 1)
        anchor.CFrame       = CFrame.new(targetPos)
        anchor.Parent       = workspace
        local att1 = Instance.new("Attachment"); att1.Parent = anchor

        local ap = Instance.new("AlignPosition")
        ap.Attachment0    = att0
        ap.Attachment1    = att1
        ap.MaxForce       = 1.2e5
        ap.Responsiveness = 250
        ap.Parent         = myRoot

        neAlignPos = ap; neAtt0 = att0; neAnchor = anchor

        task.delay(0.35, function()
            cleanAlignPos()
            pcall(function() anchor:Destroy() end)
        end)
    end)

    -- ✅ Humanoid:MoveTo fallback
    pcall(function() myHum:MoveTo(targetPos) end)

    -- Cập nhật HP ref để không trigger né lại ngay
    local hum2 = char and char:FindFirstChildOfClass("Humanoid")
    if hum2 then neTrackedHP = hum2.Health end

    task.delay(0.18, function() dodgeActive = false end)
end

-- Hook TẤT CẢ parts của enemy character
-- Kể cả tool weapon được equip — đây là nguồn đòn chém
local function hookEnemyChar(char)
    if not char then return end

    local function hookPart(part)
        if not part:IsA("BasePart") then return end
        local c = part.Touched:Connect(function(hit)
            if not STATE.autoNe then return end
            local myChar = LocalPlayer.Character
            if not myChar then return end
            -- Part của địch chạm vào bất kỳ phần nào của mình = đòn chém
            if hit:IsDescendantOf(myChar) then
                -- hitOrigin = vị trí vũ khí/tay địch lúc đó
                doDodge(part.Position)
            end
        end)
        table.insert(neTouchConns, c)
    end

    -- Hook tất cả parts hiện tại (body + tool trong tay)
    for _, d in ipairs(char:GetDescendants()) do hookPart(d) end
    -- Hook khi equip tool mới
    local c1 = char.DescendantAdded:Connect(function(d)
        task.wait(0.03); hookPart(d)
    end)
    table.insert(neTouchConns, c1)
end

local function startAutoNe()
    for _, c in ipairs(neConns)      do pcall(function() c:Disconnect() end) end
    for _, c in ipairs(neTouchConns) do pcall(function() c:Disconnect() end) end
    neConns = {}; neTouchConns = {}
    if autoNeHbConn then autoNeHbConn:Disconnect(); autoNeHbConn = nil end
    cleanAlignPos()

    local _, _, myHum = getMyChar()
    neTrackedHP = myHum and myHum.Health or 100

    -- Heartbeat: HP-drop fallback (khi Touched event miss)
    autoNeHbConn = RunService.Heartbeat:Connect(function()
        if not STATE.autoNe then return end
        local _, _, hum = getMyChar()
        if not hum or hum.Health <= 0 then return end
        local curHP = hum.Health
        if curHP < neTrackedHP - 0.5 then
            doDodge(nil)  -- không biết hitOrigin → dùng fallback dir
        end
        neTrackedHP = curHP
    end)

    -- Proximity guard: địch vào 4.5 studs → né phòng thủ
    task.spawn(function()
        while STATE.autoNe do
            task.wait(0.08)
            local _, myRoot, _ = getMyChar()
            if myRoot then
                local eRoot, dist = findNearestEnemy()
                if eRoot and dist < 4.5 then
                    doDodge(eRoot.Position)
                end
            end
        end
    end)

    -- Hook tất cả enemy hiện có
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer then
            hookEnemyChar(p.Character)
            local c = p.CharacterAdded:Connect(function(char)
                task.wait(0.5)
                if STATE.autoNe then hookEnemyChar(char) end
            end)
            table.insert(neConns, c)
        end
    end

    local c2 = Players.PlayerAdded:Connect(function(p)
        local c = p.CharacterAdded:Connect(function(char)
            task.wait(0.5)
            if STATE.autoNe then hookEnemyChar(char) end
        end)
        table.insert(neConns, c)
    end)
    table.insert(neConns, c2)
end

local function stopAutoNe()
    for _, c in ipairs(neConns)      do pcall(function() c:Disconnect() end) end
    for _, c in ipairs(neTouchConns) do pcall(function() c:Disconnect() end) end
    neConns = {}; neTouchConns = {}
    if autoNeHbConn then autoNeHbConn:Disconnect(); autoNeHbConn = nil end
    cleanAlignPos()
    dodgeActive = false
end

--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 2: TĂNG SÁT THƯƠNG v6 — x3 HIT REPEAT
-- ████████████████████████████████████████████████
-- Kỹ thuật v6:
--   ✅ Khi chém trúng địch (Touched event):
--      → Fire damage remote ĐÚNG 3 lần liên tiếp
--      → Tức là mỗi đòn chém = 3 đòn damage vào server
--   ✅ Scan toàn bộ RemoteEvent/Function để tìm đúng remote
--   ✅ Hitbox mở rộng để tăng tỉ lệ chém trúng
--   ✅ Proximity loop backup: khi trong tầm → fire 3x
--==================================================
local boostConns    = {}
local boostHbConn   = nil
local boostSwingCD  = {}

local DAMAGE_KEYWORDS = {
    "damage","hit","attack","slash","strike","dmg","deal",
    "hurt","stab","wound","combat","swing","melee","punch",
    "fight","battle","kill","harm","injure","cut","sword",
}

local function findDamageRemotes()
    local result = {}
    local function scan(parent)
        for _, v in ipairs(parent:GetDescendants()) do
            if v:IsA("RemoteEvent") or v:IsA("RemoteFunction") then
                local n = v.Name:lower()
                for _, kw in ipairs(DAMAGE_KEYWORDS) do
                    if n:find(kw) then table.insert(result, v); break end
                end
            end
        end
    end
    pcall(function() scan(game:GetService("ReplicatedStorage")) end)
    pcall(function() scan(game:GetService("ReplicatedFirst"))   end)
    pcall(function() scan(workspace) end)
    return result
end

-- Fire remote ĐÚNG 3 lần — x3 damage
local function fireRemoteX3(remote, victimChar)
    if not remote or not victimChar then return end
    local victHum = victimChar:FindFirstChildOfClass("Humanoid")
    if not victHum or victHum.Health <= 0 then return end
    local hitPos = victimChar.PrimaryPart and victimChar.PrimaryPart.Position
                   or Vector3.new(0,0,0)

    -- Signatures phổ biến nhất của PvP/dueling games
    local sigs = {
        function() remote:FireServer(victimChar, hitPos) end,
        function() remote:FireServer(victHum) end,
        function() remote:FireServer(victimChar) end,
        function() remote:FireServer(victHum, hitPos) end,
    }

    -- Fire 3 lần = x3 damage
    for i = 1, 3 do
        for _, sig in ipairs(sigs) do pcall(sig) end
        if i < 3 then task.wait(0.008) end  -- 8ms gap giữa các hit
    end

    -- TakeDamage cho NPC / non-FE-strict games
    local extra = victHum.MaxHealth * 0.08
    pcall(function() victHum:TakeDamage(extra * 3) end)
end

-- Hitbox mở rộng gắn lên weapon
local function makeBoostHitbox(weapPart)
    for _, d in ipairs(weapPart.Parent:GetChildren()) do
        if d.Name == "SDST_BHB" then pcall(function() d:Destroy() end) end
    end

    local hb = Instance.new("Part")
    hb.Name           = "SDST_BHB"
    hb.Size           = weapPart.Size + Vector3.new(1.8, 1.8, 1.8)
    hb.Transparency   = 1
    hb.CanCollide     = false
    hb.Anchored       = false
    hb.Massless       = true
    hb.CastShadow     = false
    pcall(function() hb.CanQuery = false end)
    hb.CFrame         = weapPart.CFrame

    local weld = Instance.new("WeldConstraint")
    weld.Part0 = hb; weld.Part1 = weapPart; weld.Parent = hb
    hb.Parent  = weapPart.Parent

    local hitCD      = {}
    local dmgRemotes = findDamageRemotes()

    local c = hb.Touched:Connect(function(hit)
        if not STATE.damageBoost then return end
        local victChar = hit:FindFirstAncestorOfClass("Model")
        if not victChar or victChar == LocalPlayer.Character then return end
        local victHum = victChar:FindFirstChildOfClass("Humanoid")
        if not victHum or victHum.Health <= 0 then return end

        local vid = tostring(victChar)
        local now = tick()
        if hitCD[vid] and (now - hitCD[vid]) < 0.18 then return end
        hitCD[vid] = now

        -- Fire x3 vào tất cả damage remote tìm được
        for _, rem in ipairs(dmgRemotes) do
            fireRemoteX3(rem, victChar)
        end
    end)

    table.insert(boostConns, c)
    table.insert(boostConns, {
        Disconnect = function()
            pcall(function() c:Disconnect() end)
            pcall(function() hb:Destroy() end)
        end
    })
end

local function hookTool(tool)
    local dmgRemotes = findDamageRemotes()
    local hitCD      = {}

    for _, part in ipairs(tool:GetDescendants()) do
        if part:IsA("BasePart") and part.Name ~= "SDST_BHB" then
            local c = part.Touched:Connect(function(hit)
                if not STATE.damageBoost then return end
                local victChar = hit:FindFirstAncestorOfClass("Model")
                if not victChar or victChar == LocalPlayer.Character then return end
                local victHum = victChar:FindFirstChildOfClass("Humanoid")
                if not victHum or victHum.Health <= 0 then return end

                local vid = tostring(victChar)
                local now = tick()
                if boostSwingCD[vid] and (now - boostSwingCD[vid]) < 0.15 then return end
                boostSwingCD[vid] = now

                -- x3: fire remote 3 lần
                for _, rem in ipairs(dmgRemotes) do
                    fireRemoteX3(rem, victChar)
                end
            end)
            table.insert(boostConns, c)
            pcall(function() makeBoostHitbox(part) end)
        end
    end
end

-- Proximity loop: backup khi Touched miss
local function startProxLoop()
    if boostHbConn then boostHbConn:Disconnect(); boostHbConn = nil end
    local proxCD     = {}
    local dmgRemotes = findDamageRemotes()

    boostHbConn = RunService.Heartbeat:Connect(function()
        if not STATE.damageBoost then return end
        local char, myRoot, _ = getMyChar()
        if not myRoot then return end

        local hasTool = false
        for _, obj in ipairs(char:GetChildren()) do
            if obj:IsA("Tool") then hasTool = true; break end
        end
        if not hasTool then return end

        local now = tick()
        for _, p in ipairs(Players:GetPlayers()) do
            if p ~= LocalPlayer and p.Character then
                local eRoot = p.Character:FindFirstChild("HumanoidRootPart")
                local eHum  = p.Character:FindFirstChildOfClass("Humanoid")
                if eRoot and eHum and eHum.Health > 0 then
                    local dist = (eRoot.Position - myRoot.Position).Magnitude
                    if dist < 6 then
                        local pid = tostring(p.UserId)
                        if not proxCD[pid] or (now - proxCD[pid]) > 0.22 then
                            proxCD[pid] = now
                            for _, rem in ipairs(dmgRemotes) do
                                fireRemoteX3(rem, p.Character)
                            end
                        end
                    end
                end
            end
        end
    end)
end

local function startDamageBoost()
    for _, c in ipairs(boostConns) do pcall(function() c:Disconnect() end) end
    boostConns = {}; boostSwingCD = {}

    local char, _, _ = getMyChar()
    if char then
        for _, obj in ipairs(char:GetChildren()) do
            if obj:IsA("Tool") then hookTool(obj) end
        end
        local c = char.ChildAdded:Connect(function(obj)
            if obj:IsA("Tool") and STATE.damageBoost then
                task.wait(0.08); hookTool(obj)
            end
        end)
        table.insert(boostConns, c)
    end

    startProxLoop()
end

local function stopDamageBoost()
    for _, c in ipairs(boostConns) do pcall(function() c:Disconnect() end) end
    boostConns = {}
    if boostHbConn then boostHbConn:Disconnect(); boostHbConn = nil end
    local char = LocalPlayer.Character
    if char then
        for _, d in ipairs(char:GetDescendants()) do
            if d.Name == "SDST_BHB" then pcall(function() d:Destroy() end) end
        end
    end
end

--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 3: SCAN VŨ KHÍ ĐỊCH — WEAPON INTEL
-- ████████████████████████████████████████████████
-- Scan toàn bộ thông tin vũ khí địch đang cầm:
--   ✅ Tên vũ khí (Tool.Name)
--   ✅ Ước tính damage (scan NumberValue "Damage"/"Power")
--   ✅ Danh sách skill (tên các ClickDetector / Script con)
--   ✅ Loại vũ khí (melee/ranged/magic) dựa trên parts
--   ✅ Cập nhật realtime khi địch đổi vũ khí
--   ✅ Hiển thị bảng UI trong tab VŨ KHÍ ĐỊCH
--==================================================
local weaponScanConn = nil
local weaponScanHb   = nil
local weaponData     = {}   -- {[playerName] = {name, damage, skills, type}}
local weaponUILabels = {}   -- label refs để update realtime

-- Scan một Tool để lấy thông tin
local function scanTool(tool)
    if not tool then return nil end
    local info = {
        name    = tool.Name,
        damage  = 0,
        skills  = {},
        wtype   = "Melee",    -- mặc định melee
    }

    -- Tìm giá trị damage trong tool
    local dmgKeys = {"Damage","damage","DMG","Power","power","Force","BaseDamage","AttackDamage"}
    for _, key in ipairs(dmgKeys) do
        local v = tool:FindFirstChild(key, true)
        if v and (v:IsA("NumberValue") or v:IsA("IntValue")) then
            if v.Value > 0 then
                info.damage = v.Value
                break
            end
        end
        -- Cũng check Configuration/Settings folder
        local cfg = tool:FindFirstChild("Configuration") or tool:FindFirstChild("Settings")
        if cfg then
            local vv = cfg:FindFirstChild(key)
            if vv and (vv:IsA("NumberValue") or vv:IsA("IntValue")) then
                if vv.Value > 0 then info.damage = vv.Value; break end
            end
        end
    end

    -- Phát hiện loại vũ khí
    for _, d in ipairs(tool:GetDescendants()) do
        if d:IsA("Script") or d:IsA("LocalScript") then
            local sn = d.Name:lower()
            if sn:find("gun") or sn:find("shoot") or sn:find("bullet") or sn:find("fire") then
                info.wtype = "Ranged 🔫"
            elseif sn:find("magic") or sn:find("spell") or sn:find("aura") then
                info.wtype = "Magic ✨"
            end
        end
        -- ClickDetector = thường là skill/ability
        if d:IsA("ClickDetector") and d.Name ~= "" then
            table.insert(info.skills, d.Name)
        end
        -- RemoteEvent bên trong tool = skill
        if d:IsA("RemoteEvent") or d:IsA("RemoteFunction") then
            local rn = d.Name
            if rn ~= "Hit" and rn ~= "Damage" and rn ~= "" then
                table.insert(info.skills, rn)
            end
        end
        -- NumberValue tên lạ trong tool = có thể là cooldown/charge = skill hint
        if d:IsA("StringValue") and d.Name:lower():find("skill") then
            table.insert(info.skills, d.Value ~= "" and d.Value or d.Name)
        end
    end

    -- Deduplicate skills
    local seen = {}
    local uniq = {}
    for _, s in ipairs(info.skills) do
        if not seen[s] then seen[s] = true; table.insert(uniq, s) end
    end
    info.skills = uniq

    return info
end

-- Scan tất cả enemies hiện tại
local function scanAllEnemies()
    local result = {}
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer and p.Character then
            local toolInHand = nil
            -- Tool được equip nằm trực tiếp trong Character
            for _, obj in ipairs(p.Character:GetChildren()) do
                if obj:IsA("Tool") then toolInHand = obj; break end
            end
            -- Cũng check Backpack (tool chưa equip)
            local toolInBag = nil
            local bag = p:FindFirstChild("Backpack")
            if bag then
                for _, obj in ipairs(bag:GetChildren()) do
                    if obj:IsA("Tool") then toolInBag = obj; break end
                end
            end

            local info = nil
            if toolInHand then
                info = scanTool(toolInHand)
                info.equipped = true
            elseif toolInBag then
                info = scanTool(toolInBag)
                info.equipped = false
            else
                info = { name = "—", damage = 0, skills = {}, wtype = "—", equipped = false }
            end
            result[p.Name] = info
        end
    end
    return result
end

-- Label reference để update realtime
local weaponPanelContent = nil  -- ScrollingFrame content frame

local function rebuildWeaponPanel()
    if not weaponPanelContent then return end
    -- Xóa nội dung cũ
    for _, c in ipairs(weaponPanelContent:GetChildren()) do
        if c:IsA("Frame") or c:IsA("TextLabel") then c:Destroy() end
    end

    local data = scanAllEnemies()
    local yOff = 0
    local hasAny = false

    for playerName, info in pairs(data) do
        hasAny = true

        -- Card cho mỗi player
        local card = Instance.new("Frame", weaponPanelContent)
        card.Size             = UDim2.new(1, -10, 0, 90)
        card.Position         = UDim2.fromOffset(5, yOff)
        card.BackgroundColor3 = Color3.fromRGB(14, 14, 30)
        card.BorderSizePixel  = 0
        Instance.new("UICorner", card).CornerRadius = UDim.new(0, 8)
        local cs = Instance.new("UIStroke", card)
        cs.Color = info.equipped
            and Color3.fromRGB(220, 80, 80)   -- đỏ = đang cầm
            or  Color3.fromRGB(50, 50, 80)    -- mờ = trong túi

        -- Tên player + status
        local pLbl = Instance.new("TextLabel", card)
        pLbl.Size             = UDim2.new(1, -10, 0, 18)
        pLbl.Position         = UDim2.fromOffset(8, 4)
        pLbl.BackgroundTransparency = 1
        pLbl.Text             = (info.equipped and "⚔️ " or "🎒 ") .. playerName
        pLbl.TextColor3       = info.equipped
            and Color3.fromRGB(255, 120, 120)
            or  Color3.fromRGB(160, 160, 190)
        pLbl.TextSize         = 11
        pLbl.Font             = Enum.Font.GothamBold
        pLbl.TextXAlignment   = Enum.TextXAlignment.Left

        -- Tên vũ khí
        local wLbl = Instance.new("TextLabel", card)
        wLbl.Size             = UDim2.new(1, -10, 0, 16)
        wLbl.Position         = UDim2.fromOffset(8, 22)
        wLbl.BackgroundTransparency = 1
        wLbl.Text             = "🗡️ " .. info.name .. "  |  " .. info.wtype
        wLbl.TextColor3       = Color3.fromRGB(220, 220, 240)
        wLbl.TextSize         = 10
        wLbl.Font             = Enum.Font.GothamBold
        wLbl.TextXAlignment   = Enum.TextXAlignment.Left

        -- Damage
        local dLbl = Instance.new("TextLabel", card)
        dLbl.Size             = UDim2.new(1, -10, 0, 14)
        dLbl.Position         = UDim2.fromOffset(8, 38)
        dLbl.BackgroundTransparency = 1
        dLbl.Text             = "💥 Damage: " .. (info.damage > 0 and tostring(info.damage) or "Không rõ")
        dLbl.TextColor3       = info.damage > 0
            and Color3.fromRGB(255, 160, 80)
            or  Color3.fromRGB(150, 150, 170)
        dLbl.TextSize         = 10
        dLbl.Font             = Enum.Font.Gotham
        dLbl.TextXAlignment   = Enum.TextXAlignment.Left

        -- Skills
        local skillText = #info.skills > 0
            and ("🔮 Skills: " .. table.concat(info.skills, " | "))
            or  "🔮 Skills: Không phát hiện"
        local sLbl = Instance.new("TextLabel", card)
        sLbl.Size             = UDim2.new(1, -10, 0, 28)
        sLbl.Position         = UDim2.fromOffset(8, 52)
        sLbl.BackgroundTransparency = 1
        sLbl.Text             = skillText
        sLbl.TextColor3       = Color3.fromRGB(140, 200, 255)
        sLbl.TextSize         = 9
        sLbl.Font             = Enum.Font.Gotham
        sLbl.TextXAlignment   = Enum.TextXAlignment.Left
        sLbl.TextWrapped      = true

        yOff = yOff + 96
    end

    if not hasAny then
        local noLbl = Instance.new("TextLabel", weaponPanelContent)
        noLbl.Size             = UDim2.new(1, 0, 0, 40)
        noLbl.Position         = UDim2.fromOffset(0, 20)
        noLbl.BackgroundTransparency = 1
        noLbl.Text             = "Không có địch nào trong trận"
        noLbl.TextColor3       = Color3.fromRGB(140, 140, 160)
        noLbl.TextSize         = 11
        noLbl.Font             = Enum.Font.Gotham
        noLbl.TextXAlignment   = Enum.TextXAlignment.Center
    end

    -- Cập nhật canvas size
    local pan = weaponPanelContent.Parent
    if pan and pan:IsA("ScrollingFrame") then
        pan.CanvasSize = UDim2.fromOffset(0, math.max(yOff + 10, 50))
    end
end

local function startWeaponScan()
    if weaponScanHb then weaponScanHb:Disconnect(); weaponScanHb = nil end

    -- Cập nhật ngay lập tức
    rebuildWeaponPanel()

    -- Cập nhật mỗi 1.5 giây
    local lastScan = tick()
    weaponScanHb = RunService.Heartbeat:Connect(function()
        if not STATE.weaponScan then return end
        local now = tick()
        if now - lastScan >= 1.5 then
            lastScan = now
            rebuildWeaponPanel()
        end
    end)

    -- Hook khi player đổi vũ khí
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer and p.Character then
            local c = p.Character.ChildAdded:Connect(function(obj)
                if obj:IsA("Tool") then task.wait(0.1); rebuildWeaponPanel() end
            end)
            table.insert(neConns, c)
            local c2 = p.Character.ChildRemoved:Connect(function(obj)
                if obj:IsA("Tool") then task.wait(0.1); rebuildWeaponPanel() end
            end)
            table.insert(neConns, c2)
        end
    end
end

local function stopWeaponScan()
    if weaponScanHb then weaponScanHb:Disconnect(); weaponScanHb = nil end
    -- Xóa nội dung panel
    if weaponPanelContent then
        for _, c in ipairs(weaponPanelContent:GetChildren()) do
            if c:IsA("Frame") or c:IsA("TextLabel") then c:Destroy() end
        end
        local noLbl = Instance.new("TextLabel", weaponPanelContent)
        noLbl.Size             = UDim2.new(1, 0, 0, 40)
        noLbl.Position         = UDim2.fromOffset(0, 20)
        noLbl.BackgroundTransparency = 1
        noLbl.Text             = "Bật Scan để xem thông tin vũ khí địch"
        noLbl.TextColor3       = Color3.fromRGB(140, 140, 160)
        noLbl.TextSize         = 11
        noLbl.Font             = Enum.Font.Gotham
        noLbl.TextXAlignment   = Enum.TextXAlignment.Center
    end
end


--==================================================
-- RE-APPLY KHI RESPAWN
--==================================================
LocalPlayer.CharacterAdded:Connect(function(char)
    task.wait(1.2)
    if STATE.autoNe       then startAutoNe()          end
    if STATE.damageBoost  then startDamageBoost()     end
end)

--==================================================
-- THIẾT KẾ GUI — MENU NGANG (giữ nguyên v3)
--==================================================
local GUI_W = 660
local GUI_H = 230
local HDR_H = 40

local rootGui = Instance.new("ScreenGui")
rootGui.Name            = "SDST_Menu"
rootGui.ResetOnSpawn    = false
rootGui.ZIndexBehavior  = Enum.ZIndexBehavior.Sibling
rootGui.IgnoreGuiInset  = true
rootGui.DisplayOrder    = 999
rootGui.Parent          = LocalPlayer:WaitForChild("PlayerGui")

local mainF = Instance.new("Frame", rootGui)
mainF.Name             = "MainFrame"
mainF.Size             = UDim2.fromOffset(GUI_W, GUI_H)
mainF.Position         = UDim2.new(0.5, -GUI_W/2, 0.02, 0)
mainF.BackgroundColor3 = Color3.fromRGB(8, 9, 18)
mainF.BorderSizePixel  = 0
mainF.ClipsDescendants = true
Instance.new("UICorner", mainF).CornerRadius = UDim.new(0, 16)

local mainStroke = Instance.new("UIStroke", mainF)
mainStroke.Color     = Color3.fromRGB(160, 40, 40)
mainStroke.Thickness = 2

local bgGrad = Instance.new("UIGradient", mainF)
bgGrad.Color = ColorSequence.new{
    ColorSequenceKeypoint.new(0,   Color3.fromRGB(14, 12, 28)),
    ColorSequenceKeypoint.new(0.5, Color3.fromRGB(10, 9,  20)),
    ColorSequenceKeypoint.new(1,   Color3.fromRGB(8,  7,  16)),
}
bgGrad.Rotation = 145

local hdr = Instance.new("Frame", mainF)
hdr.Name             = "Header"
hdr.Size             = UDim2.new(1, 0, 0, HDR_H)
hdr.BackgroundColor3 = Color3.fromRGB(140, 25, 25)
hdr.BorderSizePixel  = 0

local hdrGrad = Instance.new("UIGradient", hdr)
hdrGrad.Color = ColorSequence.new{
    ColorSequenceKeypoint.new(0,   Color3.fromRGB(200, 40,  40)),
    ColorSequenceKeypoint.new(0.4, Color3.fromRGB(150, 25,  25)),
    ColorSequenceKeypoint.new(1,   Color3.fromRGB(100, 15,  15)),
}

local iconLbl = Instance.new("TextLabel", hdr)
iconLbl.Size             = UDim2.fromOffset(36, HDR_H)
iconLbl.Position         = UDim2.fromOffset(10, 0)
iconLbl.BackgroundTransparency = 1
iconLbl.Text             = "⚔️"
iconLbl.TextSize         = 20
iconLbl.Font             = Enum.Font.GothamBold
iconLbl.TextColor3       = Color3.fromRGB(255, 255, 255)
iconLbl.TextXAlignment   = Enum.TextXAlignment.Center

local titleLbl = Instance.new("TextLabel", hdr)
titleLbl.Size             = UDim2.new(1, -230, 1, 0)
titleLbl.Position         = UDim2.fromOffset(48, 0)
titleLbl.BackgroundTransparency = 1
titleLbl.Text             = "SÂN ĐẤU SINH TỬ  •  Menu Chiến Đấu v6.0"
titleLbl.TextColor3       = Color3.fromRGB(255, 255, 255)
titleLbl.TextSize         = 13
titleLbl.Font             = Enum.Font.GothamBold
titleLbl.TextXAlignment   = Enum.TextXAlignment.Left

local statusBadge = Instance.new("Frame", hdr)
statusBadge.Size             = UDim2.fromOffset(130, 24)
statusBadge.Position         = UDim2.new(1, -200, 0.5, -12)
statusBadge.BackgroundColor3 = isSupported
    and Color3.fromRGB(20, 140, 60)
    or  Color3.fromRGB(160, 100, 20)
statusBadge.BorderSizePixel  = 0
Instance.new("UICorner", statusBadge).CornerRadius = UDim.new(0, 8)

local statusLbl = Instance.new("TextLabel", statusBadge)
statusLbl.Size             = UDim2.fromScale(1, 1)
statusLbl.BackgroundTransparency = 1
statusLbl.Text             = isSupported and "✅ HỖ TRỢ" or "⚠️  THỰC NGHIỆM"
statusLbl.TextColor3       = Color3.fromRGB(255, 255, 255)
statusLbl.TextSize         = 11
statusLbl.Font             = Enum.Font.GothamBold
statusLbl.TextXAlignment   = Enum.TextXAlignment.Center

local minBtn = Instance.new("TextButton", hdr)
minBtn.Size             = UDim2.fromOffset(50, 26)
minBtn.Position         = UDim2.new(1, -58, 0.5, -13)
minBtn.BackgroundColor3 = Color3.fromRGB(60, 15, 15)
minBtn.BorderSizePixel  = 0
minBtn.Text             = "—"
minBtn.TextColor3       = Color3.fromRGB(255, 180, 180)
minBtn.TextSize         = 15
minBtn.Font             = Enum.Font.GothamBold
Instance.new("UICorner", minBtn).CornerRadius = UDim.new(0, 7)

-- Drag
do
    local drag, dStart, dPos = false, nil, nil
    hdr.InputBegan:Connect(function(i)
        if i.UserInputType == Enum.UserInputType.MouseButton1
        or i.UserInputType == Enum.UserInputType.Touch then
            drag   = true
            dStart = i.Position
            dPos   = mainF.Position
        end
    end)
    UserInputService.InputChanged:Connect(function(i)
        if not drag then return end
        if i.UserInputType == Enum.UserInputType.MouseMovement
        or i.UserInputType == Enum.UserInputType.Touch then
            local d = i.Position - dStart
            mainF.Position = UDim2.new(
                dPos.X.Scale, dPos.X.Offset + d.X,
                dPos.Y.Scale, dPos.Y.Offset + d.Y
            )
        end
    end)
    UserInputService.InputEnded:Connect(function(i)
        if i.UserInputType == Enum.UserInputType.MouseButton1
        or i.UserInputType == Enum.UserInputType.Touch then
            drag = false
        end
    end)
end

local bodyF = Instance.new("Frame", mainF)
bodyF.Name             = "Body"
bodyF.Size             = UDim2.new(1, 0, 1, -HDR_H)
bodyF.Position         = UDim2.fromOffset(0, HDR_H)
bodyF.BackgroundTransparency = 1

local collapsed = false
local function setCollapsed(v)
    collapsed = v
    bodyF.Visible = not v
    mainF.Size = v and UDim2.fromOffset(GUI_W, HDR_H) or UDim2.fromOffset(GUI_W, GUI_H)
    minBtn.Text = v and "+" or "—"
end
minBtn.Activated:Connect(function() setCollapsed(not collapsed) end)

-- Tab System
local TAB_W  = 100
local TABS   = {"NÉ", "TẤN CÔNG", "VŨ KHÍ ĐỊCH", "INFO"}
local TAB_ICONS = {["NÉ"]="🌀", ["TẤN CÔNG"]="⚔️", ["VŨ KHÍ ĐỊCH"]="🔎", ["INFO"]="ℹ️"}
local TAB_COLORS = {
    ["NÉ"]       = Color3.fromRGB(120, 60, 220),
    ["TẤN CÔNG"] = Color3.fromRGB(220, 55, 55),
    ["VŨ KHÍ ĐỊCH"]= Color3.fromRGB(100, 200, 255),
    ["INFO"]     = Color3.fromRGB(90, 180, 255),
}
local tabBtns   = {}
local tabPanels = {}

local tabBar = Instance.new("Frame", bodyF)
tabBar.Size             = UDim2.fromOffset(TAB_W, GUI_H - HDR_H)
tabBar.BackgroundColor3 = Color3.fromRGB(10, 10, 22)
tabBar.BorderSizePixel  = 0

local divLine = Instance.new("Frame", tabBar)
divLine.Size             = UDim2.fromOffset(2, GUI_H - HDR_H)
divLine.Position         = UDim2.new(1, -2, 0, 0)
divLine.BackgroundColor3 = Color3.fromRGB(160, 40, 40)
divLine.BackgroundTransparency = 0.5

local contentF = Instance.new("Frame", bodyF)
contentF.Name             = "Content"
contentF.Size             = UDim2.new(1, -TAB_W, 1, 0)
contentF.Position         = UDim2.fromOffset(TAB_W, 0)
contentF.BackgroundTransparency = 1
contentF.ClipsDescendants = true

local activeTab = nil
local function switchTab(name)
    activeTab = name
    for _, n in ipairs(TABS) do
        local btn = tabBtns[n]
        local pan = tabPanels[n]
        if not btn or not pan then continue end
        if n == name then
            btn.BackgroundColor3 = TAB_COLORS[n]
            btn.TextColor3       = Color3.fromRGB(255, 255, 255)
            local ind = btn:FindFirstChild("ActiveInd")
            if not ind then
                ind = Instance.new("Frame", btn)
                ind.Name             = "ActiveInd"
                ind.Size             = UDim2.fromOffset(3, btn.Size.Y.Offset)
                ind.Position         = UDim2.new(1, -3, 0, 0)
                ind.BackgroundColor3 = Color3.fromRGB(255, 255, 255)
                ind.BackgroundTransparency = 0.4
                ind.BorderSizePixel  = 0
            end
            ind.Visible = true
            pan.Visible = true
        else
            btn.BackgroundColor3 = Color3.fromRGB(16, 16, 32)
            btn.TextColor3       = Color3.fromRGB(130, 130, 155)
            local ind = btn:FindFirstChild("ActiveInd")
            if ind then ind.Visible = false end
            pan.Visible = false
        end
    end
end

for i, name in ipairs(TABS) do
    local tabH = math.floor((GUI_H - HDR_H) / #TABS)
    local btn  = Instance.new("TextButton", tabBar)
    btn.Size             = UDim2.fromOffset(TAB_W, tabH - 2)
    btn.Position         = UDim2.fromOffset(0, (i - 1) * tabH + 1)
    btn.BackgroundColor3 = Color3.fromRGB(16, 16, 32)
    btn.BorderSizePixel  = 0
    btn.Text             = TAB_ICONS[name] .. "\n" .. name
    btn.TextColor3       = Color3.fromRGB(130, 130, 155)
    btn.TextSize         = 10
    btn.Font             = Enum.Font.GothamBold
    btn.AutoButtonColor  = false
    Instance.new("UICorner", btn).CornerRadius = UDim.new(0, 6)
    tabBtns[name] = btn

    local pan = Instance.new("ScrollingFrame", contentF)
    pan.Name                    = "Panel_" .. name
    pan.Size                    = UDim2.fromScale(1, 1)
    pan.BackgroundTransparency  = 1
    pan.Visible                 = false
    pan.ScrollBarThickness      = 3
    pan.ScrollBarImageColor3    = Color3.fromRGB(200, 50, 50)
    pan.CanvasSize              = UDim2.fromOffset(0, 0)
    pan.AutomaticCanvasSize     = Enum.AutomaticSize.Y
    tabPanels[name] = pan

    btn.Activated:Connect(function() switchTab(name) end)
end

--==================================================
-- UI HELPER: TOGGLE BUTTON
--==================================================
local function makeToggle(parent, label, desc, yPos, getState, setState, color)
    color = color or Color3.fromRGB(200, 50, 50)

    local row = Instance.new("Frame", parent)
    row.Size             = UDim2.new(1, -20, 0, 50)
    row.Position         = UDim2.fromOffset(10, yPos)
    row.BackgroundColor3 = Color3.fromRGB(14, 14, 28)
    row.BorderSizePixel  = 0
    Instance.new("UICorner", row).CornerRadius = UDim.new(0, 10)

    local rowStroke = Instance.new("UIStroke", row)
    rowStroke.Color           = Color3.fromRGB(30, 30, 55)
    rowStroke.Thickness       = 1
    rowStroke.ApplyStrokeMode = Enum.ApplyStrokeMode.Border

    local lbl = Instance.new("TextLabel", row)
    lbl.Size             = UDim2.new(1, -90, 0, 22)
    lbl.Position         = UDim2.fromOffset(14, 6)
    lbl.BackgroundTransparency = 1
    lbl.Text             = label
    lbl.TextColor3       = Color3.fromRGB(230, 230, 240)
    lbl.TextSize         = 12
    lbl.Font             = Enum.Font.GothamBold
    lbl.TextXAlignment   = Enum.TextXAlignment.Left

    if desc and desc ~= "" then
        local dLbl = Instance.new("TextLabel", row)
        dLbl.Size             = UDim2.new(1, -90, 0, 18)
        dLbl.Position         = UDim2.fromOffset(14, 26)
        dLbl.BackgroundTransparency = 1
        dLbl.Text             = desc
        dLbl.TextColor3       = Color3.fromRGB(140, 140, 160)
        dLbl.TextSize         = 10
        dLbl.Font             = Enum.Font.Gotham
        dLbl.TextXAlignment   = Enum.TextXAlignment.Left
    end

    local track = Instance.new("Frame", row)
    track.Size             = UDim2.fromOffset(62, 28)
    track.Position         = UDim2.new(1, -76, 0.5, -14)
    track.BackgroundColor3 = Color3.fromRGB(35, 35, 55)
    track.BorderSizePixel  = 0
    Instance.new("UICorner", track).CornerRadius = UDim.new(0, 14)

    local knob = Instance.new("Frame", track)
    knob.Size             = UDim2.fromOffset(22, 22)
    knob.Position         = UDim2.fromOffset(3, 3)
    knob.BackgroundColor3 = Color3.fromRGB(100, 100, 125)
    knob.BorderSizePixel  = 0
    Instance.new("UICorner", knob).CornerRadius = UDim.new(0, 11)

    local knobLbl = Instance.new("TextLabel", track)
    knobLbl.Size             = UDim2.new(1, 0, 1, 0)
    knobLbl.BackgroundTransparency = 1
    knobLbl.Text             = "TẮT"
    knobLbl.TextColor3       = Color3.fromRGB(160, 160, 160)
    knobLbl.TextSize         = 9
    knobLbl.Font             = Enum.Font.GothamBold
    knobLbl.TextXAlignment   = Enum.TextXAlignment.Right

    local function refresh()
        local on = getState()
        if on then
            TweenService:Create(track, TweenInfo.new(0.2), {BackgroundColor3 = color}):Play()
            TweenService:Create(knob,  TweenInfo.new(0.2), {
                Position         = UDim2.fromOffset(37, 3),
                BackgroundColor3 = Color3.fromRGB(255, 255, 255),
            }):Play()
            knobLbl.Text           = "BẬT"
            knobLbl.TextColor3     = Color3.fromRGB(255, 255, 255)
            knobLbl.TextXAlignment = Enum.TextXAlignment.Left
            rowStroke.Color        = color
        else
            TweenService:Create(track, TweenInfo.new(0.2), {BackgroundColor3 = Color3.fromRGB(35, 35, 55)}):Play()
            TweenService:Create(knob,  TweenInfo.new(0.2), {
                Position         = UDim2.fromOffset(3, 3),
                BackgroundColor3 = Color3.fromRGB(100, 100, 125),
            }):Play()
            knobLbl.Text           = "TẮT"
            knobLbl.TextColor3     = Color3.fromRGB(160, 160, 160)
            knobLbl.TextXAlignment = Enum.TextXAlignment.Right
            rowStroke.Color        = Color3.fromRGB(30, 30, 55)
        end
    end

    local hitbox = Instance.new("TextButton", row)
    hitbox.Size             = UDim2.fromScale(1, 1)
    hitbox.BackgroundTransparency = 1
    hitbox.Text             = ""
    hitbox.Activated:Connect(function()
        setState(not getState())
        refresh()
    end)

    refresh()
    return refresh
end

--==================================================
-- UI HELPER: SEGMENT SELECTOR
--==================================================
local function makeSegment(parent, label, levels, getLevel, setLevel, yPos, color)
    color = color or Color3.fromRGB(200, 50, 50)

    local wrap = Instance.new("Frame", parent)
    wrap.Size             = UDim2.new(1, -20, 0, 58)
    wrap.Position         = UDim2.fromOffset(10, yPos)
    wrap.BackgroundColor3 = Color3.fromRGB(14, 14, 28)
    wrap.BorderSizePixel  = 0
    Instance.new("UICorner", wrap).CornerRadius = UDim.new(0, 10)
    local ws = Instance.new("UIStroke", wrap)
    ws.Color = Color3.fromRGB(30, 30, 55)

    local lbl = Instance.new("TextLabel", wrap)
    lbl.Size             = UDim2.new(1, -10, 0, 20)
    lbl.Position         = UDim2.fromOffset(12, 6)
    lbl.BackgroundTransparency = 1
    lbl.Text             = label
    lbl.TextColor3       = Color3.fromRGB(200, 200, 215)
    lbl.TextSize         = 11
    lbl.Font             = Enum.Font.GothamBold
    lbl.TextXAlignment   = Enum.TextXAlignment.Left

    local btnRow = Instance.new("Frame", wrap)
    btnRow.Size             = UDim2.new(1, -16, 0, 26)
    btnRow.Position         = UDim2.fromOffset(8, 26)
    btnRow.BackgroundTransparency = 1

    local segW = math.floor((GUI_W - TAB_W - 40) / #levels) - 4
    local segs = {}

    local function refreshSegs()
        local cur = getLevel()
        for j, seg in ipairs(segs) do
            local val = levels[j]
            if val == cur then
                seg.BackgroundColor3 = color
                seg.TextColor3       = Color3.fromRGB(255, 255, 255)
            else
                seg.BackgroundColor3 = Color3.fromRGB(25, 25, 45)
                seg.TextColor3       = Color3.fromRGB(140, 140, 160)
            end
        end
    end

    for j, val in ipairs(levels) do
        local seg = Instance.new("TextButton", btnRow)
        seg.Size             = UDim2.fromOffset(segW, 24)
        seg.Position         = UDim2.fromOffset((j-1) * (segW + 4), 1)
        seg.BackgroundColor3 = Color3.fromRGB(25, 25, 45)
        seg.TextColor3       = Color3.fromRGB(140, 140, 160)
        seg.Text             = val .. "%"
        seg.TextSize         = 11
        seg.Font             = Enum.Font.GothamBold
        seg.BorderSizePixel  = 0
        seg.AutoButtonColor  = false
        Instance.new("UICorner", seg).CornerRadius = UDim.new(0, 6)
        table.insert(segs, seg)
        seg.Activated:Connect(function()
            setLevel(val)
            refreshSegs()
        end)
    end

    refreshSegs()
    return refreshSegs
end

--==================================================
-- PANEL 1: AUTO NÉ
--==================================================
local pNe = tabPanels["NÉ"]
Instance.new("UIPadding", pNe).PaddingTop = UDim.new(0, 8)

local function makeSectionTitle(parent, text, yPos)
    local f = Instance.new("Frame", parent)
    f.Size             = UDim2.new(1, -20, 0, 22)
    f.Position         = UDim2.fromOffset(10, yPos)
    f.BackgroundTransparency = 1
    local line1 = Instance.new("Frame", f)
    line1.Size             = UDim2.fromOffset(20, 1)
    line1.Position         = UDim2.fromOffset(0, 11)
    line1.BackgroundColor3 = Color3.fromRGB(160, 40, 40)
    line1.BackgroundTransparency = 0.4
    local t = Instance.new("TextLabel", f)
    t.Size             = UDim2.new(1, -30, 1, 0)
    t.Position         = UDim2.fromOffset(26, 0)
    t.BackgroundTransparency = 1
    t.Text             = text
    t.TextColor3       = Color3.fromRGB(200, 80, 80)
    t.TextSize         = 11
    t.Font             = Enum.Font.GothamBold
    t.TextXAlignment   = Enum.TextXAlignment.Left
end

makeSectionTitle(pNe, "⚡ CHỨC NĂNG NÉ ĐÒNH", 0)

makeToggle(
    pNe, "🌀 Auto Né Khi Địch Chém",
    "HP poll + Touched hook + Tween CFrame dodge kép",
    26,
    function() return STATE.autoNe end,
    function(v)
        STATE.autoNe = v
        if v then
            startAutoNe()
            showNotif("🌀 Auto Né", "Đã BẬT — Tự né khi HP tụt hoặc weapon địch chạm!", Color3.fromRGB(120, 60, 220), 3)
        else
            stopAutoNe()
            showNotif("🌀 Auto Né", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(140, 60, 240)
)

local neInfo = Instance.new("Frame", pNe)
neInfo.Size             = UDim2.new(1, -20, 0, 52)
neInfo.Position         = UDim2.fromOffset(10, 82)
neInfo.BackgroundColor3 = Color3.fromRGB(50, 20, 80)
neInfo.BorderSizePixel  = 0
Instance.new("UICorner", neInfo).CornerRadius = UDim.new(0, 8)
local niStroke = Instance.new("UIStroke", neInfo)
niStroke.Color = Color3.fromRGB(120, 60, 200)

local neInfoLbl = Instance.new("TextLabel", neInfo)
neInfoLbl.Size             = UDim2.new(1, -16, 1, 0)
neInfoLbl.Position         = UDim2.fromOffset(10, 0)
neInfoLbl.BackgroundTransparency = 1
neInfoLbl.Text             = "💡 v5: Instant CFrame + AlignPosition hold + MoveTo fallback\n    Phát hiện: HP poll + Proximity scan 10fps | Cooldown: 0.5s"
neInfoLbl.TextColor3       = Color3.fromRGB(180, 140, 220)
neInfoLbl.TextSize         = 10
neInfoLbl.Font             = Enum.Font.Gotham
neInfoLbl.TextXAlignment   = Enum.TextXAlignment.Left
neInfoLbl.TextWrapped      = true

--==================================================
-- PANEL 2: TẤN CÔNG
--==================================================
local pAtk = tabPanels["TẤN CÔNG"]
Instance.new("UIPadding", pAtk).PaddingTop = UDim.new(0, 8)

makeSectionTitle(pAtk, "⚔️ TĂNG SÁT THƯƠNG", 0)

makeToggle(
    pAtk, "⚔️ Tăng Sát Thương",
    "Hitbox mở rộng + FireServer tất cả RemoteEvent damage",
    26,
    function() return STATE.damageBoost end,
    function(v)
        STATE.damageBoost = v
        if v then
            startDamageBoost()
            showNotif("⚔️ Tăng Sát Thương", "Đã BẬT — +" .. STATE.boostLevel .. "% | Hitbox + Remote scan!", Color3.fromRGB(220, 55, 55), 3)
        else
            stopDamageBoost()
            showNotif("⚔️ Tăng Sát Thương", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(220, 55, 55)
)

makeSectionTitle(pAtk, "🔢 MỨC ĐỘ TĂNG SÁT THƯƠNG", 82)

makeSegment(
    pAtk, "Chọn % tăng sát thương:",
    {30, 50, 70, 100},
    function() return STATE.boostLevel end,
    function(v)
        STATE.boostLevel = v
        if STATE.damageBoost then
            stopDamageBoost()
            startDamageBoost()
            showNotif("⚔️ Cập Nhật", "Tăng sát thương: +" .. v .. "%", Color3.fromRGB(220, 55, 55), 2)
        end
    end,
    106,
    Color3.fromRGB(220, 55, 55)
)

--==================================================
-- PANEL 3: VŨ KHÍ ĐỊCH
--==================================================
local pWep = tabPanels["VŨ KHÍ ĐỊCH"]
Instance.new("UIPadding", pWep).PaddingTop = UDim.new(0, 8)

makeSectionTitle(pWep, "🔎 THÔNG TIN VŨ KHÍ ĐỊCH", 0)

makeToggle(
    pWep, "🔎 Scan Vũ Khí Địch",
    "Tên vũ khí · Damage · Skill · Loại · Realtime update",
    26,
    function() return STATE.weaponScan end,
    function(v)
        STATE.weaponScan = v
        if v then
            startWeaponScan()
            showNotif("🔎 Weapon Scan", "Đã BẬT — Đang theo dõi vũ khí địch!", Color3.fromRGB(100, 200, 255), 3)
        else
            stopWeaponScan()
            showNotif("🔎 Weapon Scan", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(100, 200, 255)
)

-- Nút scan thủ công
local scanBtnRow = Instance.new("Frame", pWep)
scanBtnRow.Size             = UDim2.new(1, -20, 0, 30)
scanBtnRow.Position         = UDim2.fromOffset(10, 82)
scanBtnRow.BackgroundColor3 = Color3.fromRGB(20, 40, 60)
scanBtnRow.BorderSizePixel  = 0
Instance.new("UICorner", scanBtnRow).CornerRadius = UDim.new(0, 8)
local sbStroke = Instance.new("UIStroke", scanBtnRow)
sbStroke.Color = Color3.fromRGB(80, 160, 220)

local refreshBtn = Instance.new("TextButton", scanBtnRow)
refreshBtn.Size             = UDim2.fromScale(1, 1)
refreshBtn.BackgroundTransparency = 1
refreshBtn.Text             = "🔄  Refresh ngay"
refreshBtn.TextColor3       = Color3.fromRGB(100, 200, 255)
refreshBtn.TextSize         = 11
refreshBtn.Font             = Enum.Font.GothamBold
refreshBtn.Activated:Connect(function()
    rebuildWeaponPanel()
    showNotif("🔎 Refresh", "Đã quét lại vũ khí địch!", Color3.fromRGB(100, 200, 255), 2)
end)

-- Scroll area hiển thị kết quả scan
local wepScroll = Instance.new("ScrollingFrame", pWep)
wepScroll.Size                = UDim2.new(1, -20, 1, -120)
wepScroll.Position            = UDim2.fromOffset(10, 118)
wepScroll.BackgroundColor3    = Color3.fromRGB(10, 10, 22)
wepScroll.BorderSizePixel     = 0
wepScroll.ScrollBarThickness  = 3
wepScroll.ScrollBarImageColor3 = Color3.fromRGB(100, 200, 255)
wepScroll.CanvasSize          = UDim2.fromOffset(0, 0)
wepScroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
Instance.new("UICorner", wepScroll).CornerRadius = UDim.new(0, 6)

-- Content frame bên trong scroll
local wepContent = Instance.new("Frame", wepScroll)
wepContent.Size             = UDim2.fromScale(1, 0)
wepContent.AutomaticSize    = Enum.AutomaticSize.Y
wepContent.BackgroundTransparency = 1
wepContent.Name             = "WepContent"

-- Gán reference cho scan function
weaponPanelContent = wepContent

-- Placeholder text
local placeLbl = Instance.new("TextLabel", wepContent)
placeLbl.Size             = UDim2.new(1, 0, 0, 40)
placeLbl.Position         = UDim2.fromOffset(0, 10)
placeLbl.BackgroundTransparency = 1
placeLbl.Text             = "Bật Scan để xem thông tin vũ khí địch"
placeLbl.TextColor3       = Color3.fromRGB(140, 140, 160)
placeLbl.TextSize         = 11
placeLbl.Font             = Enum.Font.Gotham
placeLbl.TextXAlignment   = Enum.TextXAlignment.Center

--==================================================
-- PANEL 4: INFO
--==================================================
local pInfo = tabPanels["INFO"]
Instance.new("UIPadding", pInfo).PaddingTop = UDim.new(0, 8)

local function makeInfoRow(parent, icon, label, value, yPos, valColor)
    valColor = valColor or Color3.fromRGB(200, 200, 220)
    local row = Instance.new("Frame", parent)
    row.Size             = UDim2.new(1, -20, 0, 28)
    row.Position         = UDim2.fromOffset(10, yPos)
    row.BackgroundColor3 = Color3.fromRGB(14, 14, 28)
    row.BorderSizePixel  = 0
    Instance.new("UICorner", row).CornerRadius = UDim.new(0, 8)

    local iLbl = Instance.new("TextLabel", row)
    iLbl.Size             = UDim2.fromOffset(24, 28)
    iLbl.BackgroundTransparency = 1
    iLbl.Text             = icon
    iLbl.TextSize         = 14
    iLbl.Font             = Enum.Font.GothamBold
    iLbl.TextColor3       = Color3.fromRGB(255, 255, 255)

    local nLbl = Instance.new("TextLabel", row)
    nLbl.Size             = UDim2.new(0.5, -30, 1, 0)
    nLbl.Position         = UDim2.fromOffset(24, 0)
    nLbl.BackgroundTransparency = 1
    nLbl.Text             = label
    nLbl.TextSize         = 11
    nLbl.Font             = Enum.Font.Gotham
    nLbl.TextColor3       = Color3.fromRGB(160, 160, 180)
    nLbl.TextXAlignment   = Enum.TextXAlignment.Left

    local vLbl = Instance.new("TextLabel", row)
    vLbl.Size             = UDim2.new(0.5, 0, 1, 0)
    vLbl.Position         = UDim2.new(0.5, 0, 0, 0)
    vLbl.BackgroundTransparency = 1
    vLbl.Text             = value
    vLbl.TextSize         = 11
    vLbl.Font             = Enum.Font.GothamBold
    vLbl.TextColor3       = valColor
    vLbl.TextXAlignment   = Enum.TextXAlignment.Right
    return vLbl
end

makeSectionTitle(pInfo, "📋 THÔNG TIN SCRIPT", 0)

makeInfoRow(pInfo, "🎮", "Game hiện tại:", "Sân đấu sinh tử", 26,
    isSupported and Color3.fromRGB(50, 220, 100) or Color3.fromRGB(255, 160, 30))
makeInfoRow(pInfo, "🔑", "PlaceId:", tostring(currentPlaceId), 58, Color3.fromRGB(180, 180, 220))
makeInfoRow(pInfo, "📡", "Trạng thái:", isSupported and "✅ Hỗ trợ" or "⚠️ Thực nghiệm", 90,
    isSupported and Color3.fromRGB(50, 220, 100) or Color3.fromRGB(255, 160, 30))
makeInfoRow(pInfo, "👤", "Người chơi:", LocalPlayer.Name, 122, Color3.fromRGB(180, 180, 220))
makeInfoRow(pInfo, "📦", "Phiên bản:", "v6.0 — Né Thông Minh + x3 Hit + Scan VK", 154, Color3.fromRGB(100, 220, 255))

local supportF = Instance.new("Frame", pInfo)
supportF.Size             = UDim2.new(1, -20, 0, 50)
supportF.Position         = UDim2.fromOffset(10, 186)
supportF.BackgroundColor3 = Color3.fromRGB(10, 30, 20)
supportF.BorderSizePixel  = 0
Instance.new("UICorner", supportF).CornerRadius = UDim.new(0, 8)
local sfStroke = Instance.new("UIStroke", supportF)
sfStroke.Color = Color3.fromRGB(30, 120, 60)

local sfLbl = Instance.new("TextLabel", supportF)
sfLbl.Size             = UDim2.new(1, -16, 1, 0)
sfLbl.Position         = UDim2.fromOffset(10, 0)
sfLbl.BackgroundTransparency = 1
sfLbl.Text             = "✅ Hỗ trợ: Sân đấu sinh tử (100484168444874), Dueling Grounds (4810740296)\n❌ Không hỗ trợ: Tất cả PlaceId khác"
sfLbl.TextColor3       = Color3.fromRGB(100, 200, 140)
sfLbl.TextSize         = 10
sfLbl.Font             = Enum.Font.Gotham
sfLbl.TextXAlignment   = Enum.TextXAlignment.Left
sfLbl.TextWrapped      = true

--==================================================
-- KHỞI TẠO
--==================================================
switchTab("NÉ")

if LocalPlayer.Character then
    task.spawn(function()
        task.wait(0.5)
    end)
end

print("╔══════════════════════════════════════════╗")
print("╔══════════════════════════════════════════╗")
print("║  SDST Menu v6.0 — Auto Né + x3 + Scan   ║")
print("║  PlaceId: " .. tostring(currentPlaceId) .. "   ║")
print("║  Auto Né  : HitOrigin Dodge + AlignPos  ║")
print("║  Tăng ST  : x3 Remote Fire + BigHitbox  ║")
print("║  Scan VK  : Tên + Damage + Skill địch   ║")
print("╚══════════════════════════════════════════╝")
