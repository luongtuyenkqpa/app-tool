--[[
    ╔══════════════════════════════════════════════════════════════╗
    ║   SÂN ĐẤU SINH TỬ — Menu Chiến Đấu v3.0                    ║
    ║   Game: [BATTLEPASS ⭐] Sân đấu sinh tử                     ║
    ║   PlaceId: 100484168444874                                   ║
    ║   Chức năng: Auto Né | Tăng ST | Giảm ST nhận              ║
    ║   v3.0: Fix Auto Né, Fix Tăng ST, Fix Giảm ST              ║
    ╚══════════════════════════════════════════════════════════════╝
--]]

--==================================================
-- KIỂM TRA GAME HỖ TRỢ
--==================================================
local SUPPORTED_PLACE_IDS = {
    [100484168444874] = true,   -- Sân đấu sinh tử (Battlepass)
    [4810740296]      = true,   -- Dueling Grounds bản gốc
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
local HttpService      = game:GetService("HttpService")

local LocalPlayer = Players.LocalPlayer
local Camera      = workspace.CurrentCamera

--==================================================
-- STATE CHÍNH
--==================================================
local STATE = {
    autoNe          = false,   -- Auto né khi địch chém
    damageBoost     = false,   -- Tăng sát thương
    damageReduct    = false,   -- Giảm sát thương nhận
    boostLevel      = 30,      -- % tăng ST: 30/50/70/100
    reductLevel     = 30,      -- % giảm ST nhận: 30/50/70/100
}

-- Hooks gốc
local originalTakeDamage = nil
local originalDealDamage = nil
local neConnection       = nil
local boostConnection    = nil
local reductConnection   = nil

--==================================================
-- THÔNG BÁO NOTIFICATION
--==================================================
local function showNotif(title, msg, color, duration)
    duration = duration or 3

    local gui = LocalPlayer:FindFirstChild("PlayerGui")
    if not gui then return end

    -- Tạo ScreenGui tạm
    local sGui = Instance.new("ScreenGui")
    sGui.Name         = "SDST_Notif_" .. tostring(tick())
    sGui.ResetOnSpawn = false
    sGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    sGui.IgnoreGuiInset = true
    sGui.Parent       = gui

    local W, H = 340, 70
    local frame = Instance.new("Frame", sGui)
    frame.Size             = UDim2.fromOffset(W, H)
    frame.Position         = UDim2.new(1, W + 10, 0, 80)  -- xuất hiện từ phải
    frame.BackgroundColor3 = Color3.fromRGB(12, 12, 22)
    frame.BorderSizePixel  = 0
    frame.AnchorPoint      = Vector2.new(0, 0)
    Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 12)
    local stroke = Instance.new("UIStroke", frame)
    stroke.Color     = color or Color3.fromRGB(200, 60, 60)
    stroke.Thickness = 2

    -- Thanh màu bên trái
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

    -- Animate in
    TweenService:Create(frame, TweenInfo.new(0.35, Enum.EasingStyle.Quart, Enum.EasingDirection.Out), {
        Position = UDim2.new(1, -(W + 14), 0, 80)
    }):Play()

    -- Auto dismiss
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
        Color3.fromRGB(50, 220, 100),
        5
    )
    print("[SDST v2.0] ✅ Script tải thành công! PlaceId: " .. currentPlaceId)
else
    showNotif(
        "⚠️  Game không được hỗ trợ đầy đủ!",
        "PlaceId: " .. tostring(currentPlaceId) .. "\nMột số chức năng có thể không hoạt động.",
        Color3.fromRGB(255, 160, 30),
        6
    )
    print("[SDST v2.0] ⚠️  PlaceId không khớp: " .. tostring(currentPlaceId))
    print("[SDST v2.0]    Hỗ trợ: 100484168444874 | 4810740296")
    print("[SDST v2.0]    Menu vẫn được hiển thị để thử nghiệm.")
end

-- Thông báo game hỗ trợ
task.delay(0.5, function()
    if isSupported then
        print("[SDST v2.0] Game HỖ TRỢ: Sân đấu sinh tử ✅")
    end
    print("[SDST v2.0] Danh sách game HỖ TRỢ:")
    print("  → 100484168444874  [BATTLEPASS ⭐] Sân đấu sinh tử")
    print("  → 4810740296        Dueling Grounds (gốc)")
    print("[SDST v2.0] Danh sách game KHÔNG HỖ TRỢ:")
    print("  → Tất cả PlaceId khác ngoài danh sách trên")
end)

--==================================================
-- CÁC HÀM CHIẾN ĐẤU
--==================================================

--==================================================
-- LOGIC AUTO NÉ v3 — Hook trực tiếp vào Touched của weapon địch
-- Khi vũ khí địch chạm vào nhân vật ta → né ngay lập tức
--==================================================
local neConns      = {}  -- kết nối Touched từng weapon địch
local autoNeConn   = nil -- Heartbeat scan weapon địch mới
local lastDodgeTime = 0
local DODGE_COOLDOWN = 1.2  -- giây, tránh né liên tục

-- Né bằng cách dịch chuyển CFrame nhân vật sang bên cạnh/sau lưng địch
local function doDodge(enemyRoot)
    local now = tick()
    if now - lastDodgeTime < DODGE_COOLDOWN then return end
    lastDodgeTime = now

    local myChar = LocalPlayer.Character
    local myRoot = myChar and myChar:FindFirstChild("HumanoidRootPart")
    local myHum  = myChar and myChar:FindFirstChildOfClass("Humanoid")
    if not myRoot or not myHum or myHum.Health <= 0 then return end

    -- Tính hướng né: vuông góc với hướng nhìn của địch, hoặc ra sau
    local dodgeOffset
    if enemyRoot then
        -- Vec từ địch → mình
        local toMe = (myRoot.Position - enemyRoot.Position)
        toMe = Vector3.new(toMe.X, 0, toMe.Z)
        if toMe.Magnitude > 0.1 then
            toMe = toMe.Unit
        else
            toMe = Vector3.new(1, 0, 0)
        end
        -- Né sang bên (cross product với Y)
        local side = toMe:Cross(Vector3.new(0, 1, 0)).Unit
        -- Chọn ngẫu nhiên trái hoặc phải, + thêm thành phần ra sau
        local sign = (math.random(0, 1) == 0) and 1 or -1
        dodgeOffset = (side * sign * 14) + (toMe * 8)
    else
        -- Không biết địch ở đâu → né ngẫu nhiên
        local angle = math.random() * math.pi * 2
        dodgeOffset = Vector3.new(math.cos(angle) * 14, 0, math.sin(angle) * 14)
    end

    -- Dịch chuyển CFrame (teleport nhỏ sang bên) + bật nhảy
    local newPos = myRoot.Position + dodgeOffset + Vector3.new(0, 0.5, 0)
    myRoot.CFrame = CFrame.new(newPos, newPos + myRoot.CFrame.LookVector)

    -- Thêm lực đẩy để trông tự nhiên hơn
    pcall(function()
        local bv = Instance.new("BodyVelocity")
        bv.Velocity  = dodgeOffset.Unit * 30 + Vector3.new(0, 10, 0)
        bv.MaxForce  = Vector3.new(8e4, 8e4, 8e4)
        bv.P         = 8e4
        bv.Parent    = myRoot
        game:GetService("Debris"):AddItem(bv, 0.12)
    end)
end

-- Hook Touched vào 1 Part của weapon địch
local function hookWeaponPart(part, enemyRoot)
    local c = part.Touched:Connect(function(hit)
        if not STATE.autoNe then return end
        local myChar = LocalPlayer.Character
        if not myChar then return end
        -- Chỉ né khi weapon địch THỰC SỰ chạm vào nhân vật mình
        if hit:IsDescendantOf(myChar) then
            doDodge(enemyRoot)
        end
    end)
    table.insert(neConns, c)
end

-- Hook toàn bộ weapon hiện có của 1 enemy player
local function hookEnemyWeapons(enemyPlayer)
    local char = enemyPlayer.Character
    if not char then return end
    local eRoot = char:FindFirstChild("HumanoidRootPart")

    -- Scan tool đang equipped
    for _, obj in ipairs(char:GetChildren()) do
        if obj:IsA("Tool") then
            for _, part in ipairs(obj:GetDescendants()) do
                if part:IsA("BasePart") then
                    hookWeaponPart(part, eRoot)
                end
            end
        end
    end

    -- Theo dõi tool mới được trang bị
    local c = char.ChildAdded:Connect(function(obj)
        if not STATE.autoNe then return end
        if obj:IsA("Tool") then
            task.wait(0.05) -- đợi tool load xong
            local eR = char:FindFirstChild("HumanoidRootPart")
            for _, part in ipairs(obj:GetDescendants()) do
                if part:IsA("BasePart") then
                    hookWeaponPart(part, eR)
                end
            end
            -- Cũng hook DescendantAdded (part load sau)
            obj.DescendantAdded:Connect(function(desc)
                if desc:IsA("BasePart") and STATE.autoNe then
                    hookWeaponPart(desc, eR)
                end
            end)
        end
    end)
    table.insert(neConns, c)
end

local function startAutoNe()
    -- Xoá kết nối cũ
    for _, c in ipairs(neConns) do pcall(function() c:Disconnect() end) end
    neConns = {}
    if autoNeConn then autoNeConn:Disconnect() autoNeConn = nil end

    -- Hook tất cả enemy hiện tại
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer then hookEnemyWeapons(p) end
    end

    -- Heartbeat: hook enemy mới join hoặc respawn
    autoNeConn = RunService.Heartbeat:Connect(function()
        if not STATE.autoNe then return end
    end)

    -- PlayerAdded / CharacterAdded để hook enemy mới
    Players.PlayerAdded:Connect(function(p)
        p.CharacterAdded:Connect(function()
            task.wait(0.5)
            if STATE.autoNe then hookEnemyWeapons(p) end
        end)
    end)
    for _, p in ipairs(Players:GetPlayers()) do
        if p ~= LocalPlayer then
            p.CharacterAdded:Connect(function()
                task.wait(0.5)
                if STATE.autoNe then hookEnemyWeapons(p) end
            end)
        end
    end
end

local function stopAutoNe()
    for _, c in ipairs(neConns) do pcall(function() c:Disconnect() end) end
    neConns = {}
    if autoNeConn then autoNeConn:Disconnect() autoNeConn = nil end
end

--==================================================
-- LOGIC TĂNG SÁT THƯƠNG v3
-- Hook RemoteEvent/RemoteFunction mà game dùng để xử lý damage
-- Đồng thời hook Touched của weapon mình để gây extra damage
--==================================================
local dmgBoostConns = {}
local dmgBoostConn  = nil

-- Tìm RemoteEvent damage trong game (Dueling Grounds pattern)
local function findDamageRemotes()
    local remotes = {}
    local function scan(obj)
        for _, v in ipairs(obj:GetChildren()) do
            if (v:IsA("RemoteEvent") or v:IsA("RemoteFunction")) then
                local n = v.Name:lower()
                if n:find("damage") or n:find("hit") or n:find("attack")
                or n:find("slash") or n:find("strike") or n:find("dmg") then
                    table.insert(remotes, v)
                end
            end
            if #v:GetChildren() > 0 then scan(v) end
        end
    end
    scan(workspace)
    scan(game:GetService("ReplicatedStorage"))
    return remotes
end

local function startDamageBoost()
    -- Xoá hook cũ
    for _, c in ipairs(dmgBoostConns) do pcall(function() c:Disconnect() end) end
    dmgBoostConns = {}
    if dmgBoostConn then dmgBoostConn:Disconnect() dmgBoostConn = nil end

    local boostMult = 1 + (STATE.boostLevel / 100)  -- ví dụ 1.3 cho 30%

    -- PHƯƠNG PHÁP CHÍNH: Hook Touched của tất cả BasePart trong weapon của mình
    -- Khi weapon của mình Touched enemy → gây thêm damage đúng bằng % đã chọn
    local function hookMyWeapon(tool)
        -- Lấy Handle và tất cả part của tool
        for _, part in ipairs(tool:GetDescendants()) do
            if part:IsA("BasePart") then
                local c = part.Touched:Connect(function(hit)
                    if not STATE.damageBoost then return end
                    -- Kiểm tra hit có phải nhân vật địch không
                    local victimChar = hit:FindFirstAncestorOfClass("Model")
                    if not victimChar then return end
                    local victimHum = victimChar:FindFirstChildOfClass("Humanoid")
                    if not victimHum or victimHum.Health <= 0 then return end
                    -- Không phải mình
                    local victimPlayer = Players:GetPlayerFromCharacter(victimChar)
                    if victimPlayer == LocalPlayer then return end
                    if not victimPlayer and victimChar == LocalPlayer.Character then return end

                    -- Tính extra damage: maxHealth * boostLevel% / vài lần
                    -- Dùng MaxHealth làm base để scale hợp lý
                    local baseDmg = victimHum.MaxHealth * (STATE.boostLevel / 100) * 0.18
                    baseDmg = math.max(baseDmg, 3)
                    pcall(function() victimHum:TakeDamage(baseDmg) end)
                end)
                table.insert(dmgBoostConns, c)
            end
        end
        -- Cũng theo dõi Part được thêm sau
        local c2 = tool.DescendantAdded:Connect(function(desc)
            if desc:IsA("BasePart") and STATE.damageBoost then
                local c = desc.Touched:Connect(function(hit)
                    if not STATE.damageBoost then return end
                    local victimChar = hit:FindFirstAncestorOfClass("Model")
                    if not victimChar then return end
                    local victimHum = victimChar:FindFirstChildOfClass("Humanoid")
                    if not victimHum or victimHum.Health <= 0 then return end
                    local victimPlayer = Players:GetPlayerFromCharacter(victimChar)
                    if victimPlayer == LocalPlayer then return end
                    local baseDmg = victimHum.MaxHealth * (STATE.boostLevel / 100) * 0.18
                    baseDmg = math.max(baseDmg, 3)
                    pcall(function() victimHum:TakeDamage(baseDmg) end)
                end)
                table.insert(dmgBoostConns, c)
            end
        end)
        table.insert(dmgBoostConns, c2)
    end

    -- Hook tool đang có trong tay
    local myChar = LocalPlayer.Character
    if myChar then
        for _, obj in ipairs(myChar:GetChildren()) do
            if obj:IsA("Tool") then hookMyWeapon(obj) end
        end
        -- Hook tool mới được cầm
        dmgBoostConn = myChar.ChildAdded:Connect(function(obj)
            if obj:IsA("Tool") and STATE.damageBoost then
                task.wait(0.05)
                hookMyWeapon(obj)
            end
        end)
    end

    -- PHƯƠNG PHÁP PHỤ: Scan RemoteEvent damage
    task.spawn(function()
        local remotes = findDamageRemotes()
        for _, remote in ipairs(remotes) do
            if remote:IsA("RemoteEvent") then
                -- FireServer với damage nhân thêm
                local origFire = remote.FireServer
                -- (không hook được FireServer từ client, bỏ qua)
            end
        end
    end)
end

local function stopDamageBoost()
    for _, c in ipairs(dmgBoostConns) do pcall(function() c:Disconnect() end) end
    dmgBoostConns = {}
    if dmgBoostConn then dmgBoostConn:Disconnect() dmgBoostConn = nil end
end

--==================================================
-- LOGIC GIẢM SÁT THƯƠNG NHẬN v3
-- Dùng RunService.Heartbeat để liên tục bù máu
-- Thay vì Health PropertyChanged (bị block bởi nhiều game)
--==================================================
local reductConn   = nil
local reductHbConn = nil

local function applyDamageReduction(on)
    -- Xoá kết nối cũ
    if reductConn   then reductConn:Disconnect()   reductConn   = nil end
    if reductHbConn then reductHbConn:Disconnect() reductHbConn = nil end

    if not on then return end

    local myChar = LocalPlayer.Character
    if not myChar then return end
    local myHum = myChar:FindFirstChildOfClass("Humanoid")
    if not myHum or myHum.Health <= 0 then return end

    local reductFrac    = STATE.reductLevel / 100  -- 0.3 / 0.5 / 0.7 / 1.0
    local trackedHealth = myHum.Health              -- HP tại thời điểm bắt đầu track
    local isProcessing  = false                     -- tránh đệ quy

    -- Dùng Heartbeat poll mỗi frame: nếu HP giảm → hoàn trả %
    reductHbConn = RunService.Heartbeat:Connect(function()
        if not STATE.damageReduct then return end
        if isProcessing then return end

        local curHum = myChar and myChar:FindFirstChildOfClass("Humanoid")
        if not curHum then return end

        local curHP = curHum.Health
        if curHP <= 0 then
            trackedHealth = 0
            return
        end

        if curHP < trackedHealth - 0.5 then
            -- HP vừa giảm → tính damage thực nhận
            isProcessing = true
            local dmgReceived = trackedHealth - curHP
            local refund      = dmgReceived * reductFrac
            local targetHP    = math.min(curHum.MaxHealth, curHP + refund)

            -- Bù máu bằng cách set Health trực tiếp
            pcall(function()
                curHum.Health = targetHP
            end)
            -- Cập nhật tracked sau khi bù
            trackedHealth = curHum.Health
            isProcessing = false
        else
            -- HP tăng (heal) hoặc không đổi → cập nhật tracked
            trackedHealth = curHP
        end
    end)

    -- Cũng dùng PropertyChanged làm backup (hoạt động ở một số game)
    reductConn = myHum:GetPropertyChangedSignal("Health"):Connect(function()
        -- Chỉ làm bù nếu Heartbeat chưa xử lý (trackedHealth đã được cập nhật)
        -- Heartbeat loop đã handle rồi nên signal này chỉ update trackedHealth
    end)
end

-- Re-apply khi respawn
LocalPlayer.CharacterAdded:Connect(function(char)
    task.wait(1)
    if STATE.autoNe       then startAutoNe()           end
    if STATE.damageBoost  then startDamageBoost()      end
    if STATE.damageReduct then applyDamageReduction(true) end
end)

--==================================================
-- THIẾT KẾ GUI — MENU NGANG
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

---------- MAIN FRAME ----------
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

-- Background gradient
local bgGrad = Instance.new("UIGradient", mainF)
bgGrad.Color = ColorSequence.new{
    ColorSequenceKeypoint.new(0,   Color3.fromRGB(14, 12, 28)),
    ColorSequenceKeypoint.new(0.5, Color3.fromRGB(10, 9,  20)),
    ColorSequenceKeypoint.new(1,   Color3.fromRGB(8,  7,  16)),
}
bgGrad.Rotation = 145

---------- HEADER ----------
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

-- Icon + Title
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
titleLbl.Text             = "SÂN ĐẤU SINH TỬ  •  Menu Chiến Đấu v3.0"
titleLbl.TextColor3       = Color3.fromRGB(255, 255, 255)
titleLbl.TextSize         = 13
titleLbl.Font             = Enum.Font.GothamBold
titleLbl.TextXAlignment   = Enum.TextXAlignment.Left

-- Status badge
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

-- Minimize button
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

---------- DRAG HEADER ----------
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

---------- BODY ----------
local bodyF = Instance.new("Frame", mainF)
bodyF.Name             = "Body"
bodyF.Size             = UDim2.new(1, 0, 1, -HDR_H)
bodyF.Position         = UDim2.fromOffset(0, HDR_H)
bodyF.BackgroundTransparency = 1

-- Minimize toggle
local collapsed = false
local function setCollapsed(v)
    collapsed = v
    bodyF.Visible = not v
    mainF.Size = v
        and UDim2.fromOffset(GUI_W, HDR_H)
        or  UDim2.fromOffset(GUI_W, GUI_H)
    minBtn.Text = v and "+" or "—"
end
minBtn.Activated:Connect(function() setCollapsed(not collapsed) end)

---------- TAB SYSTEM ----------
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

-- Tab sidebar
local tabBar = Instance.new("Frame", bodyF)
tabBar.Size             = UDim2.fromOffset(TAB_W, GUI_H - HDR_H)
tabBar.BackgroundColor3 = Color3.fromRGB(10, 10, 22)
tabBar.BorderSizePixel  = 0

local divLine = Instance.new("Frame", tabBar)
divLine.Size             = UDim2.fromOffset(2, GUI_H - HDR_H)
divLine.Position         = UDim2.new(1, -2, 0, 0)
divLine.BackgroundColor3 = Color3.fromRGB(160, 40, 40)
divLine.BackgroundTransparency = 0.5

-- Content area
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
            -- Thêm chỉ báo active
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
    rowStroke.Color             = Color3.fromRGB(30, 30, 55)
    rowStroke.Thickness         = 1
    rowStroke.ApplyStrokeMode   = Enum.ApplyStrokeMode.Border

    -- Label
    local lbl = Instance.new("TextLabel", row)
    lbl.Size             = UDim2.new(1, -90, 0, 22)
    lbl.Position         = UDim2.fromOffset(14, 6)
    lbl.BackgroundTransparency = 1
    lbl.Text             = label
    lbl.TextColor3       = Color3.fromRGB(230, 230, 240)
    lbl.TextSize         = 12
    lbl.Font             = Enum.Font.GothamBold
    lbl.TextXAlignment   = Enum.TextXAlignment.Left

    -- Description
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

    -- Toggle track
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
            knobLbl.Text      = "BẬT"
            knobLbl.TextColor3 = Color3.fromRGB(255, 255, 255)
            knobLbl.TextXAlignment = Enum.TextXAlignment.Left
            rowStroke.Color   = color
        else
            TweenService:Create(track, TweenInfo.new(0.2), {BackgroundColor3 = Color3.fromRGB(35, 35, 55)}):Play()
            TweenService:Create(knob,  TweenInfo.new(0.2), {
                Position         = UDim2.fromOffset(3, 3),
                BackgroundColor3 = Color3.fromRGB(100, 100, 125),
            }):Play()
            knobLbl.Text      = "TẮT"
            knobLbl.TextColor3 = Color3.fromRGB(160, 160, 160)
            knobLbl.TextXAlignment = Enum.TextXAlignment.Right
            rowStroke.Color   = Color3.fromRGB(30, 30, 55)
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
-- UI HELPER: SEGMENT SELECTOR (30/50/70/100)
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
local padding1 = Instance.new("UIPadding", pNe)
padding1.PaddingTop = UDim.new(0, 8)

-- Separator title
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

local refreshNe = makeToggle(
    pNe, "🌀 Auto Né Khi Địch Chém",
    "Tự động nhảy né khi phát hiện kẻ địch tấn công",
    26,
    function() return STATE.autoNe end,
    function(v)
        STATE.autoNe = v
        if v then
            startAutoNe()
            showNotif("🌀 Auto Né", "Đã BẬT — Sẽ tự động né khi địch tấn công!", Color3.fromRGB(120, 60, 220), 3)
        else
            stopAutoNe()
            showNotif("🌀 Auto Né", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(140, 60, 240)
)

-- Info box
local neInfo = Instance.new("Frame", pNe)
neInfo.Size             = UDim2.new(1, -20, 0, 46)
neInfo.Position         = UDim2.fromOffset(10, 82)
neInfo.BackgroundColor3 = Color3.fromRGB(50, 20, 80)
neInfo.BorderSizePixel  = 0
Instance.new("UICorner", neInfo).CornerRadius = UDim.new(0, 8)
local niStroke = Instance.new("UIStroke", neInfo)
niStroke.Color = Color3.fromRGB(120, 60, 200)
niStroke.Thickness = 1

local neInfoLbl = Instance.new("TextLabel", neInfo)
neInfoLbl.Size             = UDim2.new(1, -16, 1, 0)
neInfoLbl.Position         = UDim2.fromOffset(10, 0)
neInfoLbl.BackgroundTransparency = 1
neInfoLbl.Text             = "💡 Hook trực tiếp vũ khí địch — Né ngay khi weapon địch CHẠM vào bạn\n    Cooldown né: 1.2 giây | Né sang bên + ra sau | Không né lung tung"
neInfoLbl.TextColor3       = Color3.fromRGB(180, 140, 220)
neInfoLbl.TextSize         = 10
neInfoLbl.Font             = Enum.Font.Gotham
neInfoLbl.TextXAlignment   = Enum.TextXAlignment.Left
neInfoLbl.TextWrapped      = true

--==================================================
-- PANEL 2: TẤN CÔNG — TĂNG SÁT THƯƠNG
--==================================================
local pAtk = tabPanels["TẤN CÔNG"]
local padding2 = Instance.new("UIPadding", pAtk)
padding2.PaddingTop = UDim.new(0, 8)

makeSectionTitle(pAtk, "⚔️ TĂNG SÁT THƯƠNG", 0)

local refreshBoost = makeToggle(
    pAtk, "⚔️ Tăng Sát Thương",
    "Hook weapon — Gây thêm % MaxHP địch mỗi khi weapon chạm địch",
    26,
    function() return STATE.damageBoost end,
    function(v)
        STATE.damageBoost = v
        if v then
            startDamageBoost()
            showNotif("⚔️ Tăng Sát Thương", "Đã BẬT — +" .. STATE.boostLevel .. "% sát thương!", Color3.fromRGB(220, 55, 55), 3)
        else
            stopDamageBoost()
            showNotif("⚔️ Tăng Sát Thương", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(220, 55, 55)
)

makeSectionTitle(pAtk, "🔢 MỨC ĐỘ TĂNG SÁT THƯƠNG", 82)

local refreshBoostSeg = makeSegment(
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
-- PANEL 3: PHÒNG THỦ — GIẢM SÁT THƯƠNG
--==================================================
local pDef = tabPanels["PHÒNG THỦ"]
local padding3 = Instance.new("UIPadding", pDef)
padding3.PaddingTop = UDim.new(0, 8)

makeSectionTitle(pDef, "🛡️ GIẢM SÁT THƯƠNG NHẬN", 0)

local refreshReduct = makeToggle(
    pDef, "🛡️ Giảm Sát Thương Nhận",
    "Heartbeat bù máu — HP tụt xong được hoàn trả % ngay lập tức",
    26,
    function() return STATE.damageReduct end,
    function(v)
        STATE.damageReduct = v
        applyDamageReduction(v)
        if v then
            showNotif("🛡️ Giảm Sát Thương", "Đã BẬT — Giảm " .. STATE.reductLevel .. "% ST nhận!", Color3.fromRGB(55, 130, 220), 3)
        else
            showNotif("🛡️ Giảm Sát Thương", "Đã TẮT", Color3.fromRGB(100, 100, 130), 2)
        end
    end,
    Color3.fromRGB(55, 130, 220)
)

makeSectionTitle(pDef, "🔢 MỨC ĐỘ GIẢM SÁT THƯƠNG", 82)

local refreshReductSeg = makeSegment(
    pDef, "Chọn % giảm sát thương nhận:",
    {30, 50, 70, 100},
    function() return STATE.reductLevel end,
    function(v)
        STATE.reductLevel = v
        if STATE.damageReduct then
            applyDamageReduction(false)
            applyDamageReduction(true)
            showNotif("🛡️ Cập Nhật", "Giảm sát thương: -" .. v .. "% ST nhận", Color3.fromRGB(55, 130, 220), 2)
        end
    end,
    106,
    Color3.fromRGB(55, 130, 220)
)

-- Warning note
local warnBox = Instance.new("Frame", pDef)
warnBox.Size             = UDim2.new(1, -20, 0, 38)
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
warnLbl.Text             = "⚠️  Mức 100% = Bất tử tạm thời. Dùng cẩn thận để tránh bị phát hiện."
warnLbl.TextColor3       = Color3.fromRGB(200, 150, 80)
warnLbl.TextSize         = 10
warnLbl.Font             = Enum.Font.Gotham
warnLbl.TextXAlignment   = Enum.TextXAlignment.Left
warnLbl.TextWrapped      = true

--==================================================
-- PANEL 4: INFO
--==================================================
local pInfo = tabPanels["INFO"]
local padding4 = Instance.new("UIPadding", pInfo)
padding4.PaddingTop = UDim.new(0, 8)

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
makeInfoRow(pInfo, "🔑", "PlaceId:", tostring(currentPlaceId), 58,
    Color3.fromRGB(180, 180, 220))
makeInfoRow(pInfo, "📡", "Trạng thái:", isSupported and "✅ Hỗ trợ" or "⚠️ Thực nghiệm", 90,
    isSupported and Color3.fromRGB(50, 220, 100) or Color3.fromRGB(255, 160, 30))
makeInfoRow(pInfo, "👤", "Người chơi:", LocalPlayer.Name, 122, Color3.fromRGB(180, 180, 220))
makeInfoRow(pInfo, "📦", "Phiên bản:", "v3.0 — Fix Né/Boost/Giảm ST", 154, Color3.fromRGB(180, 180, 220))

-- Game support list
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
sfLbl.Text             = "✅ Game hỗ trợ: Sân đấu sinh tử (100484168444874), Dueling Grounds (4810740296)\n❌ Không hỗ trợ: Tất cả PlaceId khác"
sfLbl.TextColor3       = Color3.fromRGB(100, 200, 140)
sfLbl.TextSize         = 10
sfLbl.Font             = Enum.Font.Gotham
sfLbl.TextXAlignment   = Enum.TextXAlignment.Left
sfLbl.TextWrapped      = true

--==================================================
-- KHỞI TẠO TAB ĐẦU TIÊN
--==================================================
switchTab("NÉ")

--==================================================
-- APPLY CHỨC NĂNG KHI CHARACTER CÓ SẴN
--==================================================
if LocalPlayer.Character then
    task.spawn(function()
        task.wait(0.5)
        if STATE.damageReduct then applyDamageReduction(true) end
    end)
end

print("╔══════════════════════════════════════╗")
print("║  SDST Menu v3.0 — Đã tải xong!      ║")
print("║  PlaceId: " .. tostring(currentPlaceId) .. "  ║")
print("║  Game hỗ trợ: " .. (isSupported and "✅ CÓ" or "⚠️ KHÔNG") .. "                  ║")
print("║  v3: Fix Auto Né + Fix Boost + Fix Giảm ST  ║")
print("╚══════════════════════════════════════╝")
