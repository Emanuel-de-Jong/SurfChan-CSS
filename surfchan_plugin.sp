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
#define STRING_SIZE 256
// Highest amount of seperations a string in SepString can have.
// And with that also the highest the data in a SurfChan message can have.
#define MAX_STRING_SEP 10

enum MESSAGE_TYPE {
    INIT = 1,
    START = 2,
    TICK = 3,
    MOVE = 4
};

Socket g_socket;
bool g_isConnected = false;
bool g_isStarted = false;
int g_botCount = 0;
int g_tickCount = 0;
new Handle:g_buttons;
float g_mouseX = 0.0;
float g_mouseY = 0.0;
float g_currentAngles[3];
int g_client = 0;

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
    char messageStr[STRING_SIZE];
    strcopy(messageStr, sizeof(messageStr), receiveData);

    MESSAGE_TYPE messageType;
    char messageData[STRING_SIZE];

    if (!DecodeMessage(messageStr, messageType, messageData)) {
        return;
    }

    if (messageType == INIT) {
        HandleInit(messageData);
    } else if (messageType == START) {
        HandleStart(messageData);
    } else if (messageType == MOVE) {
        HandleMove(messageData);
    }
}

bool DecodeMessage(const char[] messageStr, MESSAGE_TYPE &messageType, char[] messageData) {
    if (strlen(messageStr) == 0) {
        LogError("Empty message received");
        return false;
    }

    char sepData[MAX_STRING_SEP][STRING_SIZE];
    int sepDataCount;
    SepString(messageStr, ':', sepData, sepDataCount);

    if (sepDataCount != 2) {
        LogError("Message has invalid format: %s", messageStr);
        return false;
    }

    int typeInt = StringToInt(sepData[0]);
    if (typeInt == 0) {
        LogError("Invalid message type: %s", sepData[0]);
        return false;
    }

    messageType = view_as<MESSAGE_TYPE>(typeInt);
    strcopy(messageData, STRING_SIZE, sepData[1]);
    return true;
}

void SendMessage(MESSAGE_TYPE type, const char[] data) {
    char message[STRING_SIZE];
    Format(message, sizeof(message), "%d:%s", type, data);
    
    if (g_isConnected) {
        g_socket.Send(message);
    }
}

void HandleInit(const char[] data) {
    PrintToServer("Received: %s", data);

    char ipStr[32];
    int ip = GetConVarInt(FindConVar("hostip"));
    Format(ipStr, sizeof(ipStr), "%d.%d.%d.%d",
        (ip >> 24) & 255, (ip >> 16) & 255, (ip >> 8) & 255, ip & 255);

    SendMessage(INIT, ipStr);
}

void HandleStart(const char[] data) {
    char sepData[MAX_STRING_SEP][STRING_SIZE];
    int sepDataCount;
    SepString(data, ',', sepData, sepDataCount);

    g_botCount = StringToInt(sepData[0]);
    for (int i = 0; i < g_botCount; i++) {
        float startPos[3];
        startPos[0] = StringToFloat(sepData[1]);
        startPos[1] = StringToFloat(sepData[2]);
        startPos[2] = StringToFloat(sepData[3]);
    
        g_client = CreateFakeClient("bot_1");
        ChangeClientTeam(g_client, 3);
        CS_RespawnPlayer(g_client);
    
        TeleportEntity(g_client, startPos, NULL_VECTOR, NULL_VECTOR);
    }

    g_isStarted = true;
}

void HandleMove(const char[] data) {
    char sepData[MAX_STRING_SEP][STRING_SIZE];
    int sepDataCount;
    SepString(data, ',', sepData, sepDataCount);

    g_mouseX = StringToFloat(sepData[1]);
    g_mouseY = StringToFloat(sepData[2]);

    ResetButtons();

    if (StrContains(sepData[0], "f") != -1) {
        SetTrieValue(g_buttons, "f", 1);
    }

    if (StrContains(sepData[0], "b") != -1) {
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
    if (!IsClientConnected(client) || !IsClientInGame(client) || !IsFakeClient(client) || !IsPlayerAlive(client))
    {
        return Plugin_Continue;
    }

    g_client = client;

    if (!g_isStarted) {
        return Plugin_Continue;
    }

    buttons = 0;

    vel[0] = 0.0;
    vel[1] = 0.0;
    vel[2] = 0.0;

    int isF = 0;
    GetTrieValue(g_buttons, "f", isF);
    if (isF == 1) {
        vel[0] = 100000.0;
    }

    g_currentAngles[0] = NormalizeDegree(g_currentAngles[0] + g_mouseY);
    g_currentAngles[1] = NormalizeDegree(g_currentAngles[1] + g_mouseX);

    angles[0] = g_currentAngles[0];
    angles[1] = g_currentAngles[1];
    
    TeleportEntity(client, NULL_VECTOR, g_currentAngles, NULL_VECTOR);

    return Plugin_Changed;
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

void SepString(const char[] str, const char separator, char sepData[MAX_STRING_SEP][STRING_SIZE], int &sepCount) {
    sepCount = 1;
    for (int i = 0; i < strlen(str); i++) {
        if (str[i] == separator) {
            sepCount++;
        }
    }

    char seperatorStr[2];
    seperatorStr[0] = separator;
    seperatorStr[1] = '\0';
    ExplodeString(str, seperatorStr, sepData, sepCount, STRING_SIZE);
}
