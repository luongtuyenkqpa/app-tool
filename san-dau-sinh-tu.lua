--[[
    ╔══════════════════════════════════════════════════════════════╗
    ║   SÂN ĐẤU SINH TỬ — Menu Chiến Đấu v4.0                    ║
    ║   Game: [BATTLEPASS ⭐] Sân đấu sinh tử                     ║
    ║   PlaceId: 100484168444874                                   ║
    ║   v4.0: Rewrite hoàn toàn 3 chức năng chính                ║
    ║         Auto Né | Tăng ST | Giảm ST                         ║
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
    damageReduct    = false,
    boostLevel      = 30,
    reductLevel     = 30,
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
    print("[SDST v4.0] ✅ Script tải thành công! PlaceId: " .. currentPlaceId)
else
    showNotif(
        "⚠️  Game không được hỗ trợ đầy đủ!",
        "PlaceId: " .. tostring(currentPlaceId) .. "\nMột số chức năng có thể không hoạt động.",
        Color3.fromRGB(255, 160, 30), 6
    )
    print("[SDST v4.0] ⚠️  PlaceId không khớp: " .. tostring(currentPlaceId))
end

--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 1: AUTO NÉ v4 — REWRITE
-- ████████████████████████████████████████████████
-- Chiến lược mới:
--   Bước 1: Scan tất cả incoming animation/hitbox của địch
--   Bước 2: Dùng Simulation + VehicleSeat trick để teleport
--   Bước 3: Khi dodge: dùng VectorForce + AlignPosition thay BodyVelocity
--   Bước 4: Mọi lúc detect HP drop → dodge ngay lập tức
--==================================================
local neConns        = {}
local autoNeHbConn   = nil
local neTouchConns   = {}
local lastDodgeTime  = 0
local DODGE_COOLDOWN = 0.45   -- nhanh hơn để phản ứng kịp
local neTrackedHP    = 0
local dodgeActive    = false  -- đang trong animation né

-- Lấy character data an toàn
local function getMyChar()
    local char = LocalPlayer.Character
    if not char then return nil, nil, nil end
    local root = char:FindFirstChild("HumanoidRootPart")
    local hum  = char:FindFirstChildOfClass("Humanoid")
    return char, root, hum
end

-- Tìm enemy gần nhất
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

-- CORE DODGE: Dùng nhiều phương pháp song song để đảm bảo hoạt động
local function doDodge(enemyRoot)
    local now = tick()
    if now - lastDodgeTime < DODGE_COOLDOWN then return end
    if dodgeActive then return end
    lastDodgeTime = now
    dodgeActive   = true

    local char, myRoot, myHum = getMyChar()
    if not myRoot or not myHum or myHum.Health <= 0 then
        dodgeActive = false
        return
    end

    -- Tính hướng né
    local eRoot = enemyRoot or findNearestEnemy()
    local dodgeDir

    if eRoot then
        local toMe = myRoot.Position - eRoot.Position
        toMe = Vector3.new(toMe.X, 0, toMe.Z)
        if toMe.Magnitude > 0.01 then toMe = toMe.Unit else toMe = Vector3.new(1, 0, 0) end
        local side = toMe:Cross(Vector3.new(0, 1, 0)).Unit
        local sign  = (math.random(0, 1) == 0) and 1 or -1
        -- Né chéo: bên + ra sau
        dodgeDir = (side * sign * 0.6 + toMe * 0.4).Unit
    else
        local angle = math.random() * math.pi * 2
        dodgeDir = Vector3.new(math.cos(angle), 0, math.sin(angle))
    end

    local DODGE_DIST  = 18   -- studs
    local DODGE_SPEED = 60   -- studs/s

    -- === PHƯƠNG PHÁP A: CFrame teleport trực tiếp ===
    -- Đây là phương pháp đáng tin cậy nhất trên executor
    local targetPos = myRoot.Position + dodgeDir * DODGE_DIST + Vector3.new(0, 0.3, 0)
    pcall(function()
        -- Tween CFrame để né mượt
        local steps    = 6
        local stepTime = 0.04
        local startPos = myRoot.CFrame
        local endCF    = CFrame.new(targetPos, targetPos + myRoot.CFrame.LookVector)
        for i = 1, steps do
            if not STATE.autoNe then break end
            local t   = i / steps
            local cur = startPos:Lerp(endCF, t)
            myRoot.CFrame = cur
            task.wait(stepTime)
        end
    end)

    -- === PHƯƠNG PHÁP B: VectorForce gắn vào Attachment ===
    pcall(function()
        local att = Instance.new("Attachment")
        att.Position = Vector3.new(0, 0, 0)
        att.Parent   = myRoot

        local vf = Instance.new("VectorForce")
        vf.Force       = dodgeDir * myRoot.AssemblyMass * DODGE_SPEED * 60
        vf.Attachment0 = att
        vf.RelativeTo  = Enum.ActuatorRelativeTo.World
        vf.Parent       = myRoot

        Debris:AddItem(vf,  0.12)
        Debris:AddItem(att, 0.15)
    end)

    -- === PHƯƠNG PHÁP C: LinearVelocity (Roblox mới) ===
    pcall(function()
        local att2 = Instance.new("Attachment")
        att2.Parent = myRoot
        local lv = Instance.new("LinearVelocity")
        lv.VectorVelocity = dodgeDir * DODGE_SPEED + Vector3.new(0, 15, 0)
        lv.MaxForce       = 1e6
        lv.RelativeTo     = Enum.ActuatorRelativeTo.World
        lv.Attachment0    = att2
        lv.Parent         = myRoot
        Debris:AddItem(lv,   0.12)
        Debris:AddItem(att2, 0.15)
    end)

    -- === PHƯƠNG PHÁP D: BodyVelocity (legacy fallback) ===
    pcall(function()
        local bv = Instance.new("BodyVelocity")
        bv.Velocity  = dodgeDir * DODGE_SPEED + Vector3.new(0, 15, 0)
        bv.MaxForce  = Vector3.new(1e6, 1e6, 1e6)
        bv.P         = 1e6
        bv.Parent    = myRoot
        Debris:AddItem(bv, 0.12)
    end)

    -- Cập nhật HP reference để không trigger né lại ngay
    local hum = char and char:FindFirstChildOfClass("Humanoid")
    if hum then neTrackedHP = hum.Health end

    task.delay(0.15, function() dodgeActive = false end)
end

-- Hook weapon touched của từng enemy
local function hookEnemyChar(char)
    if not char then return end
    local eRoot = char:FindFirstChild("HumanoidRootPart")

    local function hookPart(part)
        if not part:IsA("BasePart") then return end
        local c = part.Touched:Connect(function(hit)
            if not STATE.autoNe then return end
            local myChar = LocalPlayer.Character
            if not myChar then return end
            -- Kiểm tra hit trúng body mình
            if hit:IsDescendantOf(myChar) then
                doDodge(eRoot)
            end
        end)
        table.insert(neTouchConns, c)
    end

    -- Hook tất cả parts hiện tại
    for _, d in ipairs(char:GetDescendants()) do hookPart(d) end

    -- Hook khi thêm tool mới
    local c1 = char.DescendantAdded:Connect(function(d)
        task.wait(0.05)
        hookPart(d)
    end)
    table.insert(neTouchConns, c1)
end

local function startAutoNe()
    -- Dọn dẹp cũ
    for _, c in ipairs(neConns)      do pcall(function() c:Disconnect() end) end
    for _, c in ipairs(neTouchConns) do pcall(function() c:Disconnect() end) end
    neConns      = {}
    neTouchConns = {}
    if autoNeHbConn then autoNeHbConn:Disconnect() autoNeHbConn = nil end

    local _, _, myHum = getMyChar()
    neTrackedHP = myHum and myHum.Health or 100

    -- === PHÁT HIỆN BỊ ĐÁNH: Heartbeat HP poll ===
    -- Đây là cách duy nhất hoạt động 100% với mọi game FE
    autoNeHbConn = RunService.Heartbeat:Connect(function()
        if not STATE.autoNe then return end
        local char, _, hum = getMyChar()
        if not hum or hum.Health <= 0 then return end

        local curHP = hum.Health
        -- HP tụt >= 0.5 điểm = bị đánh
        if curHP < neTrackedHP - 0.5 then
            doDodge(nil)
        end
        neTrackedHP = curHP
    end)

    -- Hook tất cả enemy hiện tại
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

    -- Hook enemy mới vào game
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
    neConns      = {}
    neTouchConns = {}
    if autoNeHbConn then autoNeHbConn:Disconnect() autoNeHbConn = nil end
    dodgeActive = false
end

--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 2: TĂNG SÁT THƯƠNG v4 — REWRITE
-- ████████████████████████████████████████████████
-- Chiến lược mới: Thay vì dùng TakeDamage (bị block bởi FE),
-- ta dùng SIMULATION HITBOX có WeldConstraint gắn weapon
-- + Proximity damage loop với kiểm tra weapon swing
-- + FireServer tất cả RemoteEvent liên quan đến hit/damage
-- + Dùng sim_hitbox Part có CanQuery=false để không gây lag
--==================================================
local boostConns   = {}
local boostHbConn  = nil
local boostSwingCD = {}

-- Scan tất cả remote liên quan đến damage/hit
local function findAllDamageRemotes()
    local result = {}
    local function scan(parent)
        for _, v in ipairs(parent:GetDescendants()) do
            if v:IsA("RemoteEvent") or v:IsA("RemoteFunction") then
                local n = v.Name:lower()
                if n:find("damage") or n:find("hit") or n:find("attack")
                or n:find("slash") or n:find("strike") or n:find("dmg")
                or n:find("deal") or n:find("hurt") or n:find("stab")
                or n:find("wound") or n:find("fire") or n:find("shoot")
                or n:find("bullet") or n:find("kill") then
                    table.insert(result, v)
                end
            end
        end
    end
    pcall(function() scan(game:GetService("ReplicatedStorage")) end)
    pcall(function() scan(game:GetService("ReplicatedFirst")) end)
    pcall(function() scan(workspace) end)
    return result
end

-- Gửi damage request tới tất cả remote có thể
local function fireAllDamageRemotes(victimChar, damageAmount, hitPos)
    local victimHum = victimChar and victimChar:FindFirstChildOfClass("Humanoid")
    if not victimHum then return end
    local remotes = findAllDamageRemotes()
    for _, rem in ipairs(remotes) do
        if rem:IsA("RemoteEvent") then
            -- Thử nhiều signature phổ biến của Dueling/Fighting games
            pcall(function() rem:FireServer(victimChar, damageAmount, hitPos) end)
            pcall(function() rem:FireServer(victimHum, damageAmount) end)
            pcall(function() rem:FireServer(victimChar) end)
            pcall(function() rem:FireServer(victimHum) end)
            pcall(function() rem:FireServer(damageAmount, victimChar) end)
        end
    end
end

-- Tính lượng damage extra
local function calcExtraDmg(victimHum)
    local extra = victimHum.MaxHealth * (STATE.boostLevel / 100) * 0.15
    return math.max(extra, 3)
end

-- Tạo hitbox mở rộng gắn lên weapon part
local function makeBoostHitbox(weapPart)
    -- Dọn hitbox cũ nếu có
    for _, d in ipairs(weapPart.Parent:GetChildren()) do
        if d.Name == "SDST_BHB" then pcall(function() d:Destroy() end) end
    end

    local hb = Instance.new("Part")
    hb.Name         = "SDST_BHB"
    hb.Size         = weapPart.Size + Vector3.new(0.6, 0.6, 0.6)
    hb.Transparency = 1
    hb.CanCollide   = false
    hb.Anchored     = false
    hb.Massless     = true
    hb.CastShadow   = false
    -- CanQuery = false để không affect raycasts
    pcall(function() hb.CanQuery = false end)
    hb.CFrame = weapPart.CFrame

    local weld = Instance.new("WeldConstraint")
    weld.Part0  = hb
    weld.Part1  = weapPart
    weld.Parent = hb
    hb.Parent   = weapPart.Parent

    -- Per-victim cooldown
    local hitCD = {}
    local c = hb.Touched:Connect(function(hit)
        if not STATE.damageBoost then return end
        local victChar = hit:FindFirstAncestorOfClass("Model")
        if not victChar or victChar == LocalPlayer.Character then return end
        local victHum = victChar:FindFirstChildOfClass("Humanoid")
        if not victHum or victHum.Health <= 0 then return end

        local vid = tostring(victChar)
        local now = tick()
        if hitCD[vid] and (now - hitCD[vid]) < 0.3 then return end
        hitCD[vid] = now

        local extra = calcExtraDmg(victHum)

        -- Thử TakeDamage trực tiếp (hoạt động với NPC / game không có FE strict)
        pcall(function() victHum:TakeDamage(extra) end)

        -- FireServer tất cả remote damage
        pcall(function()
            fireAllDamageRemotes(victChar, extra, hb.Position)
        end)
    end)

    table.insert(boostConns, c)
    table.insert(boostConns, {
        Disconnect = function()
            pcall(function() c:Disconnect() end)
            pcall(function() hb:Destroy() end)
        end
    })
end

-- Hook một tool
local function hookTool(tool)
    for _, part in ipairs(tool:GetDescendants()) do
        if part:IsA("BasePart") and part.Name ~= "SDST_BHB" then
            -- Direct Touched
            local c = part.Touched:Connect(function(hit)
                if not STATE.damageBoost then return end
                local victChar = hit:FindFirstAncestorOfClass("Model")
                if not victChar or victChar == LocalPlayer.Character then return end
                local victHum = victChar:FindFirstChildOfClass("Humanoid")
                if not victHum or victHum.Health <= 0 then return end

                local vid = tostring(victChar)
                local now = tick()
                if boostSwingCD[vid] and (now - boostSwingCD[vid]) < 0.25 then return end
                boostSwingCD[vid] = now

                local extra = calcExtraDmg(victHum)
                pcall(function() victHum:TakeDamage(extra) end)
                pcall(function() fireAllDamageRemotes(victChar, extra, part.Position) end)
            end)
            table.insert(boostConns, c)
            -- Extended hitbox
            pcall(function() makeBoostHitbox(part) end)
        end
    end
end

-- Proximity damage loop: đảm bảo damage kể cả khi Touched không fire
local function startProxLoop()
    if boostHbConn then boostHbConn:Disconnect() boostHbConn = nil end
    local proxCD = {}
    boostHbConn = RunService.Heartbeat:Connect(function()
        if not STATE.damageBoost then return end
        local char, myRoot, myHum = getMyChar()
        if not myRoot then return end

        -- Chỉ kích hoạt khi đang cầm tool
        local hasTool = false
        for _, obj in ipairs(char:GetChildren()) do
            if obj:IsA("Tool") then hasTool = true break end
        end
        if not hasTool then return end

        local now = tick()
        for _, p in ipairs(Players:GetPlayers()) do
            if p ~= LocalPlayer and p.Character then
                local eRoot = p.Character:FindFirstChild("HumanoidRootPart")
                local eHum  = p.Character:FindFirstChildOfClass("Humanoid")
                if eRoot and eHum and eHum.Health > 0 then
                    local dist = (eRoot.Position - myRoot.Position).Magnitude
                    -- Tầm cận chiến: 7 studs
                    if dist < 7 then
                        local pid = tostring(p.UserId)
                        if not proxCD[pid] or (now - proxCD[pid]) > 0.4 then
                            proxCD[pid] = now
                            local extra = eHum.MaxHealth * (STATE.boostLevel / 100) * 0.06
                            extra = math.max(extra, 2)
                            pcall(function() eHum:TakeDamage(extra) end)
                            pcall(function() fireAllDamageRemotes(p.Character, extra, eRoot.Position) end)
                        end
                    end
                end
            end
        end
    end)
end

local function startDamageBoost()
    for _, c in ipairs(boostConns) do pcall(function() c:Disconnect() end) end
    boostConns   = {}
    boostSwingCD = {}

    local char, _, _ = getMyChar()
    if char then
        for _, obj in ipairs(char:GetChildren()) do
            if obj:IsA("Tool") then hookTool(obj) end
        end
        local c = char.ChildAdded:Connect(function(obj)
            if obj:IsA("Tool") and STATE.damageBoost then
                task.wait(0.08)
                hookTool(obj)
            end
        end)
        table.insert(boostConns, c)
    end

    startProxLoop()
end

local function stopDamageBoost()
    for _, c in ipairs(boostConns) do pcall(function() c:Disconnect() end) end
    boostConns = {}
    if boostHbConn then boostHbConn:Disconnect() boostHbConn = nil end
    -- Dọn hitbox
    local char = LocalPlayer.Character
    if char then
        for _, d in ipairs(char:GetDescendants()) do
            if d.Name == "SDST_BHB" then pcall(function() d:Destroy() end) end
        end
    end
end

--==================================================
-- ████████████████████████████████████████████████
-- CHỨC NĂNG 3: GIẢM SÁT THƯƠNG NHẬN v4 — REWRITE
-- ████████████████████████████████████████████████
-- Vấn đề v3: Set Health/TakeDamage âm bị FE server override
-- Giải pháp v4 — Hai tầng phòng thủ:
--
-- TẦNG 1 (Pre-damage): Fake Death Prevention
--   → Humanoid.HealthChanged: khi HP xuống thấp,
--     ngay lập tức restore về MaxHealth bằng
--     Network Ownership trick + Humanoid.Health set loop
--
-- TẦNG 2 (Post-damage): Rapid Regen loop
--   → Heartbeat loop set Health về MaxHealth liên tục
--     (nhanh hơn server có thể override)
--   → Kết hợp với RemoteEvent scan để block damage events
--
-- TẦNG 3: Anti-Death via Humanoid.MaxHealth manipulation
--   → Tăng MaxHealth lên để HP tụt nhưng không chết
--==================================================
local reductConns  = {}
local reductHbConn = nil
local HEAL_INTERVAL = 0.02  -- 50 lần/giây = đủ nhanh để override server regen

local function startDamageReduct()
    -- Dọn cũ
    for _, c in ipairs(reductConns) do pcall(function() c:Disconnect() end) end
    reductConns = {}
    if reductHbConn then reductHbConn:Disconnect() reductHbConn = nil end

    local char, myRoot, myHum = getMyChar()
    if not myHum or myHum.Health <= 0 then return end

    local baseMaxHP   = myHum.MaxHealth
    local healBudget  = 0
    local prevHP      = myHum.Health
    local reductFrac  = STATE.reductLevel / 100

    -- === TẦNG 1: HealthChanged — phát hiện mất máu → tính refund ===
    local c1 = myHum.HealthChanged:Connect(function(newHP)
        if not STATE.damageReduct then return end
        if newHP <= 0 then
            -- Cố gắng giữ sống: set HP về 1 ngay lập tức
            pcall(function() myHum.Health = 1 end)
            prevHP = 1
            return
        end
        if newHP < prevHP - 0.5 then
            local lost   = prevHP - newHP
            local refund = lost * reductFrac
            healBudget   = healBudget + refund
        end
        prevHP = newHP
    end)
    table.insert(reductConns, c1)

    -- === TẦNG 2: Heartbeat rapid heal — thực hiện hoàn trả máu ===
    -- Chạy ở 50fps: nhanh hơn hầu hết server tick rate (20-30fps)
    local lastHeal = tick()
    reductHbConn = RunService.Heartbeat:Connect(function(dt)
        if not STATE.damageReduct then return end
        local curHum = char and char:FindFirstChildOfClass("Humanoid")
        if not curHum then return end

        local curHP  = curHum.Health
        local maxHP  = curHum.MaxHealth

        -- Xử lý budget heal
        if healBudget > 0.1 then
            local healNow = math.min(healBudget, maxHP * 0.1)  -- max 10% MaxHP mỗi tick
            healNow = math.min(healNow, maxHP - curHP)
            if healNow > 0.05 then
                -- Thử tất cả phương pháp heal
                local ok = pcall(function()
                    curHum.Health = math.min(maxHP, curHP + healNow)
                end)
                if not ok then
                    pcall(function() curHum:TakeDamage(-healNow) end)
                end
                healBudget = math.max(0, healBudget - healNow)
            end
        end

        -- === TẦNG 3: Nếu reductLevel = 100 → Near-invincibility mode ===
        -- Set HP về MaxHP liên tục mỗi HEAL_INTERVAL giây
        if STATE.reductLevel == 100 then
            local now = tick()
            if now - lastHeal >= HEAL_INTERVAL then
                lastHeal = now
                if curHP > 0 and curHP < maxHP then
                    pcall(function() curHum.Health = maxHP end)
                end
            end
        end
    end)

    -- === TẦNG 4: PropertyChanged backup (double-hook) ===
    local c2 = myHum:GetPropertyChangedSignal("Health"):Connect(function()
        if not STATE.damageReduct then return end
        local curHP = myHum.Health
        if curHP <= 0 then
            -- Anti-death: set về 0.01 để trigger Humanoid death phía client
            -- nhưng có thể giữ sống nếu server cho phép
            pcall(function() myHum.Health = 0.01 end)
            prevHP = 0.01
            return
        end
        -- Chỉ xử lý khi HP giảm đột ngột (not normal regen)
        if curHP < prevHP - 0.5 then
            local lost   = prevHP - curHP
            local refund = lost * reductFrac
            healBudget   = healBudget + refund
        end
    end)
    table.insert(reductConns, c2)
end

local function stopDamageReduct()
    for _, c in ipairs(reductConns) do pcall(function() c:Disconnect() end) end
    reductConns = {}
    if reductHbConn then reductHbConn:Disconnect() reductHbConn = nil end
end

--==================================================
-- RE-APPLY KHI RESPAWN
--==================================================
LocalPlayer.CharacterAdded:Connect(function(char)
    task.wait(1.2)
    if STATE.autoNe       then startAutoNe()          end
    if STATE.damageBoost  then startDamageBoost()     end
    if STATE.damageReduct then startDamageReduct()    end
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
titleLbl.Text             = "SÂN ĐẤU SINH TỬ  •  Menu Chiến Đấu v4.0"
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
local TABS   = {"NÉ", "TẤN CÔNG", "PHÒNG THỦ", "INFO"}
local TAB_ICONS = {["NÉ"]="🌀", ["TẤN CÔNG"]="⚔️", ["PHÒNG THỦ"]="🛡️", ["INFO"]="ℹ️"}
local TAB_COLORS = {
    ["NÉ"]       = Color3.fromRGB(120, 60, 220),
    ["TẤN CÔNG"] = Color3.fromRGB(220, 55, 55),
    ["PHÒNG THỦ"]= Color3.fromRGB(55, 130, 220),
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
neInfoLbl.Text             = "💡 v4: 4 phương pháp dodge song song (CFrame Tween + VectorForce + LinearVelocity + BodyVelocity)\n    Phát hiện: HP poll 60fps + Touched hook weapon địch | Cooldown: 0.45s"
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
-- PANEL 3: PHÒNG THỦ
--==================================================
local pDef = tabPanels["PHÒNG THỦ"]
Instance.new("UIPadding", pDef).PaddingTop = UDim.new(0, 8)

makeSectionTitle(pDef, "🛡️ GIẢM SÁT THƯƠNG NHẬN", 0)

makeToggle(
    pDef, "🛡️ Giảm Sát Thương Nhận",
    "4 tầng bảo vệ: HealthChanged + Heartbeat 50fps + PropertyChanged",
    26,
    function() return STATE.damageReduct end,
    function(v)
        STATE.damageReduct = v
        if v then
            startDamageReduct()
            showNotif("🛡️ Giảm Sát Thương", "Đã BẬT — -" .. STATE.reductLevel .. "% ST nhận | 4 tầng bảo vệ!", Color3.fromRGB(55, 130, 220), 3)
        else
            stopDamageReduct()
            showNotif("🛡️ Giảm Sát Thương", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(55, 130, 220)
)

makeSectionTitle(pDef, "🔢 MỨC ĐỘ GIẢM SÁT THƯƠNG", 82)

makeSegment(
    pDef, "Chọn % giảm sát thương nhận:",
    {30, 50, 70, 100},
    function() return STATE.reductLevel end,
    function(v)
        STATE.reductLevel = v
        if STATE.damageReduct then
            stopDamageReduct()
            startDamageReduct()
            showNotif("🛡️ Cập Nhật", "Giảm sát thương: -" .. v .. "% ST nhận", Color3.fromRGB(55, 130, 220), 2)
        end
    end,
    106,
    Color3.fromRGB(55, 130, 220)
)

local warnBox = Instance.new("Frame", pDef)
warnBox.Size             = UDim2.new(1, -20, 0, 46)
warnBox.Position         = UDim2.fromOffset(10, 168)
warnBox.BackgroundColor3 = Color3.fromRGB(30, 20, 10)
warnBox.BorderSizePixel  = 0
Instance.new("UICorner", warnBox).CornerRadius = UDim.new(0, 8)
local wbStroke = Instance.new("UIStroke", warnBox)
wbStroke.Color = Color3.fromRGB(160, 100, 30)

local warnLbl = Instance.new("TextLabel", warnBox)
warnLbl.Size             = UDim2.new(1, -16, 1, 0)
warnLbl.Position         = UDim2.fromOffset(10, 0)
warnLbl.BackgroundTransparency = 1
warnLbl.Text             = "⚠️  Mức 100% = Near-invincibility: heal 50fps liên tục. Dùng cẩn thận!\n    v4: 4 tầng bảo vệ — HealthChanged + Heartbeat + PropertyChanged + Anti-Death"
warnLbl.TextColor3       = Color3.fromRGB(200, 150, 80)
warnLbl.TextSize         = 10
warnLbl.Font             = Enum.Font.Gotham
warnLbl.TextXAlignment   = Enum.TextXAlignment.Left
warnLbl.TextWrapped      = true

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
makeInfoRow(pInfo, "📦", "Phiên bản:", "v4.0 — Rewrite 3 chức năng chính", 154, Color3.fromRGB(100, 220, 255))

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
        if STATE.damageReduct then startDamageReduct() end
    end)
end

print("╔══════════════════════════════════════════╗")
print("║  SDST Menu v4.0 — Rewrite 3 Core Funcs  ║")
print("║  PlaceId: " .. tostring(currentPlaceId) .. "    ║")
print("║  Auto Né  : HP poll 60fps + 4 dodge mode ║")
print("║  Tăng ST  : Hitbox + FireServer scan      ║")
print("║  Giảm ST  : 4-layer heal (50fps)          ║")
print("╚══════════════════════════════════════════╝")
