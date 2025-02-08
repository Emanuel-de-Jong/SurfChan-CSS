#include <sourcemod>
#include <cstrike>
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

public void OnPluginStart() {
    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
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
        SetBot();
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
    if (g_botId == -1) {
        return;
    }

    PrintToServer("Moving...");

    if (StrContains(data, "move_forward") != -1) {
        FakeClientCommand(g_botId, "+forward");
    }

    if (StrContains(data, "rotate_right") != -1) {
        float angles[3];
        GetClientEyeAngles(g_botId, angles);
        angles[1] += 10.0;
        TeleportEntity(g_botId, NULL_VECTOR, angles, NULL_VECTOR);
    }
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

void SetBot() {
    int botId = CreateFakeClient("bot");
    
    SetEntProp(botId, Prop_Data, "m_nButtons", 0);
    SetEntProp(botId, Prop_Data, "m_afButtonForced", 0);
    SetEntProp(botId, Prop_Data, "m_afButtonLast", 0);
    SetEntProp(botId, Prop_Data, "m_bAllowAutoMovement", 0);

    ChangeClientTeam(botId, 3);
    CS_RespawnPlayer(botId);

    g_botId = botId;
}
