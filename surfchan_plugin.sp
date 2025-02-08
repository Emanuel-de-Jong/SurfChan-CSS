#include <sourcemod>
#include <sdktools>
#include <socket>

enum MESSAGE_TYPE {
    TEST = 1,
    START = 2,
    TICK = 3,
    MOVE = 4
};

bool DecodeMessage(const char[] messageStr, MESSAGE_TYPE &messageType, char[] data, int dataLen) {
    if (strlen(messageStr) == 0) {
        LogError("Empty message received");
        return false;
    }

    int delimiterPos = StrContains(messageStr, ":");
    if (delimiterPos == -1) {
        LogError("Message has invalid format: %s", messageStr);
        return false;
    }

    char typeStr[8];
    char dataStr[256];
    
    strcopy(typeStr, sizeof(typeStr), messageStr);
    typeStr[delimiterPos] = '\0';  // Terminate at delimiter
    strcopy(dataStr, sizeof(dataStr), messageStr[delimiterPos + 1]);

    int typeInt = StringToInt(typeStr);
    if (typeInt == 0) {
        LogError("Invalid message type: %s", typeStr);
        return false;
    }

    messageType = view_as<MESSAGE_TYPE>(typeInt);
    strcopy(data, dataLen, dataStr);
    return true;
}

public Plugin myinfo = {
    name = "surfchan_plugin",
    author = "Anon",
    description = "SurfChan",
    version = "0.1"
};

#define SERVER_HOST "127.0.0.1"
#define SERVER_PORT 27015
#define TICKS_PER_MESSAGE 30

Socket g_socket;
bool g_isConnected = false;
bool g_isStarted = false;
int g_tickCount = 0;
int g_botId = -1;
int g_botCount = 0;
int g_botIds[8];

public void OnPluginStart() {
    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);

    HookEvent("round_start", OnRoundStart, EventHookMode_PostNoCopy);
    HookEvent("player_spawn", OnPlayerSpawn, EventHookMode_PostNoCopy);
}

public void OnSocketConnected(Socket socket, any data) {
    g_isConnected = true;
    PrintToServer("Connected to SurfChan.");
}

public void OnSocketDisconnected(Socket socket, any data) {
    g_isConnected = false;
    PrintToServer("Disconnected from SurfChan.");
}

public void OnSocketError(Socket socket, const int errorType, const int errorNum, any data) {
    g_isConnected = false;
    LogError("Socket error %d (errno %d).", errorType, errorNum);
}

public void OnSocketReceive(Socket socket, char[] receiveData, const int dataSize, any data) {
    char messageStr[256];
    strcopy(messageStr, sizeof(messageStr), receiveData);

    MESSAGE_TYPE messageType;
    char messageData[256];

    if (!DecodeMessage(messageStr, messageType, messageData, sizeof(messageData))) {
        return;
    }

    if (messageType == TEST) {
        PrintToServer("Received: %s", messageData);
        SendMessage(TEST, "Hello from CSS");
    } else if (messageType == START) {
        g_isStarted = true;
    } else if (messageType == MOVE) {
        Move(messageData);
    }
}

void SendMessage(MESSAGE_TYPE type, const char[] data) {
    char message[256];
    Format(message, sizeof(message), "%d:%s", type, data);
    
    if (g_isConnected) {
        g_socket.Send(message);
    }
}

void Move(const char[] data) {
    if (g_botId == -1 || !IsClientInGame(g_botId) || !IsPlayerAlive(g_botId)) {
        return;
    }

    if (StrContains(data, "move_forward") == -1) {
        FakeClientCommand(g_botId, "-forward");
    }
    else {
        FakeClientCommand(g_botId, "+forward");
    }

    if (StrContains(data, "rotate_right") != -1) {
        float angles[3];
        GetClientEyeAngles(g_botId, angles);
        angles[1] += 10.0;
        TeleportEntity(g_botId, NULL_VECTOR, angles, NULL_VECTOR);
    }

    // for (int i = 0; i < g_botCount; i++) {
    //     int botId = g_botIds[i];
    //     if (!IsClientInGame(i) || !IsPlayerAlive(botId)) {
    //         continue;
    //     }

    //     if (StrContains(data, "move_forward") == -1) {
    //         FakeClientCommand(botId, "-forward");
    //     }
    //     else {
    //         FakeClientCommand(botId, "+forward");
    //     }
    
    //     if (StrContains(data, "rotate_right") != -1) {
    //         float angles[3];
    //         GetClientEyeAngles(botId, angles);
    //         angles[1] += 10.0;
    //         TeleportEntity(botId, NULL_VECTOR, angles, NULL_VECTOR);
    //     }
    // }
}

public void OnGameFrame() {
    if (g_isConnected && g_isStarted) {
        g_tickCount++;

        if (g_tickCount >= TICKS_PER_MESSAGE) {
            g_tickCount = 0;
            SendMessage(TICK, "");
        }
    }
}

public OnRoundStart(Handle:event, const String:name[], bool:dontBroadcast) {
    PrintToServer("OnRoundStartOnRoundStartOnRoundStartOnRoundStartOnRoundStart");
    g_botId = CreateFakeClient("bot_1");
    ChangeClientTeam(g_botId, 3);
    CS_RespawnPlayer(g_botId);

    // int botCount = 0;
    // int botIds[8];
    // for (int i = 1; i <= MaxClients; i++) {
    //     if (IsClientInGame(i) && IsFakeClient(i)) {
    //         botIds[botCount] = i;
    //         botCount++;
    //     }
    // }

    // if (botCount == 0) {
    //     PrintToServer("Could not find bots");
    //     return Plugin_Handled;
    // }

    // for (int i = 0; i < botCount; i++) {
    //     int botId = botIds[i];
    //     SetEntProp(botId, Prop_Data, "m_bInDuckJump", 0);
    //     SetEntProp(botId, Prop_Data, "m_afButtonForced", 0);
    //     SetEntProp(botId, Prop_Data, "m_nButtons", 0);
    //     SetEntProp(botId, Prop_Data, "m_afButtonLast", 0);
    //     SetEntProp(botId, Prop_Data, "m_bAllowAutoMovement", 0);
    // }

    // g_botCount = botCount;
    // g_botIds = botIds;
}

public void OnPlayerSpawn(Event event, const char[] name, bool dontBroadcast) {
    PrintToServer("OnPlayerSpawnOnPlayerSpawnOnPlayerSpawn");
}
