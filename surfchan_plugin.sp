#include <sourcemod>
#include <cstrike>
#include <sdktools>
#include <socket>

public Plugin myinfo = {
    name = "surfchan_plugin",
    author = "Anon",
    description = "SurfChan",
    version = "0.1"
};

#define SERVER_HOST "127.0.0.1"
#define SERVER_PORT 27015
#define TICKS_PER_MESSAGE 1

enum MESSAGE_TYPE {
    TEST = 1,
    START = 2,
    TICK = 3,
    MOVE = 4
};

Socket g_socket;
bool g_isConnected = false;
bool g_isStarted = false;
int g_tickCount = 0;
new Handle:g_buttons;
float g_mouseX = 0.0;
float g_mouseY = 0.0;

public void OnPluginStart() {
    ResetButtons();

    HookEvent("player_spawn", OnPlayerSpawn);

    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
}

void ResetButtons() {
    if (g_buttons == INVALID_HANDLE)
    {
        g_buttons = CreateTrie();
    }
    
    SetTrieValue(g_buttons, "f", 0);
    SetTrieValue(g_buttons, "b", 0);
}

public Action OnPlayerSpawn(Event event, const char[] name, bool dontBroadcast) {
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (IsClientInGame(client) && !IsFakeClient(client))
    {
        CreateTimer(0.5, MoveToSpectator, client, TIMER_FLAG_NO_MAPCHANGE);
    }
    return Plugin_Continue;
}

public Action MoveToSpectator(Handle timer, any client) {
    if (IsClientInGame(client))
    {
        ChangeClientTeam(client, 1);
    }
    return Plugin_Continue;
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
        SetMove(messageData);
    }
}

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
    typeStr[delimiterPos] = '\0';
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

void SendMessage(MESSAGE_TYPE type, const char[] data) {
    char message[256];
    Format(message, sizeof(message), "%d:%s", type, data);
    
    if (g_isConnected) {
        g_socket.Send(message);
    }
}

void SetMove(const char[] data) {
    char buttons[256];
    char mouseStr[256];
    
    int delimiterPos = StrContains(data, ",");
    strcopy(buttons, sizeof(buttons), data);
    buttons[delimiterPos] = '\0';
    strcopy(mouseStr, sizeof(mouseStr), data[delimiterPos + 1]);

    char mouseXStr[256];
    char mouseYStr[256];

    delimiterPos = StrContains(mouseStr, ",");
    strcopy(mouseXStr, sizeof(mouseXStr), mouseStr);
    mouseXStr[delimiterPos] = '\0';
    strcopy(mouseYStr, sizeof(mouseYStr), mouseStr[delimiterPos + 1]);

    g_mouseX = StringToFloat(mouseXStr);
    g_mouseY = StringToFloat(mouseYStr);

    ResetButtons();

    if (StrContains(buttons, "f") != -1) {
        SetTrieValue(g_buttons, "f", 1);
    }

    if (StrContains(buttons, "b") != -1) {
        SetTrieValue(g_buttons, "b", 1);
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

public Action OnPlayerRunCmd(
    int client,
    int &buttons,
    int &impulse,
    float vel[3],
    float angles[3],
    int &weapon,
    int &subtype,
    int &cmdnum,
    int &tickcount,
    int &seed,
    int mouse[2]
)
{
    if (g_isStarted && IsClientConnected(client) && IsClientInGame(client) &&
        IsFakeClient(client) && IsPlayerAlive(client))
    {
        buttons = 0;

        vel[0] = 0.0;
        vel[1] = 0.0;
        vel[2] = 0.0;

        int isF = 0;
        GetTrieValue(g_buttons, "f", isF);
        if (isF == 1) {
            vel[0] = 100000.0;
        }

        angles[0] = NormalizeDegree(angles[0] + g_mouseY);
        angles[1] = NormalizeDegree(angles[1] + g_mouseX);
        
        TeleportEntity(client, NULL_VECTOR, angles, NULL_VECTOR);

        return Plugin_Changed;
    }

    return Plugin_Continue;
}

float NormalizeDegree(float degree) {
    while (degree > 180.0) {
        degree -= 360.0;
    }

    while (degree < -180.0) {
        degree += 360.0;
    }

    return degree;
}
