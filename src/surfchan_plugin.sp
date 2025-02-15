#include <sourcemod>
#include <cstrike>
#include <sdktools>
#include <socket>
#include <vphysics>

public Plugin myinfo = {
    name = "surfchan_plugin",
    author = "Anon",
    description = "SurfChan",
    version = "0.1"
};

#define SERVER_HOST "127.0.0.1"
#define SERVER_PORT 27015
#define TICKS_PER_MESSAGE 1
#define MAX_BOTS 100
#define STRING_SIZE 512
#define STRING_SIZE_BIG 2250
#define STRING_SIZE_VERY_BIG 8000
// Highest amount of seperations a string in SepString can have.
// And with that also the highest the data in a SurfChan message can have.
#define MAX_STRING_SEP 10
#define MAX_STRING_SEP_BIG 100

enum MESSAGE_TYPE {
    INIT = 1,
    START = 2,
    TICK = 3,
    MOVES = 4
};

enum struct Bot {
    float mouseX;
    float mouseY;
    float currentAngles[3];
    Handle buttons;
}

Socket g_socket;
bool g_isConnected = false;
bool g_isStarted = false;
int g_tickCount = 0;
int g_botCount = 0;
int g_botIds[MAX_BOTS];
Bot g_bots[MAX_BOTS];

public void OnPluginStart() {
    HookEvent("player_spawn", OnPlayerSpawn);

    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.SetOption(SocketReceiveBuffer, STRING_SIZE_BIG);
    g_socket.SetOption(SocketSendBuffer, STRING_SIZE_VERY_BIG);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
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
    char messageStr[STRING_SIZE_BIG];
    strcopy(messageStr, sizeof(messageStr), receiveData);

    MESSAGE_TYPE messageType;
    char messageData[STRING_SIZE_BIG];

    if (!DecodeMessage(messageStr, messageType, messageData)) {
        return;
    }

    if (messageType == INIT) {
        HandleInit(messageData);
    } else if (messageType == START) {
        HandleStart(messageData);
    } else if (messageType == MOVES) {
        HandleMoves(messageData);
    }
}

bool DecodeMessage(const char[] messageStr, MESSAGE_TYPE &messageType, char[] messageData) {
    if (strlen(messageStr) == 0) {
        LogError("Empty message received");
        return false;
    }

    char sepData[MAX_STRING_SEP_BIG][STRING_SIZE_BIG];
    int sepDataCount;
    SepStringBig(messageStr, ':', sepData, sepDataCount);

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
    strcopy(messageData, STRING_SIZE_BIG, sepData[1]);
    return true;
}

void SendMessage(MESSAGE_TYPE type, const char[] data) {
    char message[STRING_SIZE_VERY_BIG];
    Format(message, sizeof(message), "%d:%s", type, data);
    if (g_isConnected) g_socket.Send(message);
}

void HandleInit(const char[] data) {
    char sepData[MAX_STRING_SEP][STRING_SIZE];
    int sepDataCount;
    SepString(data, ',', sepData, sepDataCount);

    g_botCount = StringToInt(sepData[0]);
    for (int i = 0; i < g_botCount; i++) {
        if (i % 2 == 0) {
            ServerCommand("bot_add t");
        } else {
            ServerCommand("bot_add ct");
        }
    }

    float startAngle = StringToFloat(sepData[1]);
    CreateTimer(0.5, FindBots, startAngle, TIMER_FLAG_NO_MAPCHANGE);

    char ipStr[32];
    int ip = GetConVarInt(FindConVar("hostip"));
    Format(ipStr, sizeof(ipStr), "%d.%d.%d.%d",
        (ip >> 24) & 255, (ip >> 16) & 255, (ip >> 8) & 255, ip & 255);

    SendMessage(INIT, ipStr);
}

public Action FindBots(Handle timer, float startAngle) {
    int index = 0;
    for (int client = 1; client <= MaxClients; client++) {
        if (IsClientConnected(client) && IsFakeClient(client)) {
            g_botIds[index] = client;

            g_bots[index].currentAngles[1] = startAngle;

            g_bots[index].buttons = CreateTrie();
            ResetButtons(g_bots[index].buttons);

            index++;
        }
    }

    return Plugin_Continue;
}

void HandleStart(const char[] data) {
    char sepData[MAX_STRING_SEP][STRING_SIZE];
    int sepDataCount;
    SepString(data, ',', sepData, sepDataCount);

    float startPos[3];
    startPos[0] = StringToFloat(sepData[0]);
    startPos[1] = StringToFloat(sepData[1]);
    startPos[2] = StringToFloat(sepData[2]);

    for (int i = 0; i < g_botCount; i++) {
        TeleportEntity(g_botIds[i], startPos, g_bots[i].currentAngles, NULL_VECTOR);
    }

    g_isStarted = true;
}

void ResetButtons(Handle& buttons) {
    SetTrieValue(buttons, "f", 0);
    SetTrieValue(buttons, "b", 0);
}

void HandleMoves(const char[] data) {
    char botsData[MAX_STRING_SEP_BIG][STRING_SIZE_BIG];
    int sepDataCount;
    SepStringBig(data, ';', botsData, sepDataCount);

    for (int i = 0; i < g_botCount; i++) {
        char botData[MAX_STRING_SEP][STRING_SIZE];
        int botDataCount;
        SepString(botsData[i], ',', botData, botDataCount);

        g_bots[i].mouseX = StringToFloat(botData[1]);
        g_bots[i].mouseY = StringToFloat(botData[2]);

        ResetButtons(g_bots[i].buttons);
        if (StrContains(botData[0], "f") != -1) {
            SetTrieValue(g_bots[i].buttons, "f", 1);
        }
        if (StrContains(botData[0], "b") != -1) {
            SetTrieValue(g_bots[i].buttons, "b", 1);
        }
    }
}

public void OnGameFrame() {
    if (g_isConnected && g_isStarted) {
        g_tickCount++;

        if (g_tickCount < TICKS_PER_MESSAGE) return;
        g_tickCount = 0;

        char messageStr[STRING_SIZE_VERY_BIG];
        for (int i = 0; i < g_botCount; i++) {
            float position[3];
            GetEntPropVector(g_botIds[i], Prop_Send, "m_vecOrigin", position);

            float velocity[3];
            GetEntPropVector(g_botIds[i], Prop_Data, "m_vecVelocity", velocity);

            float totalVelocity = SquareRoot(velocity[0] * velocity[0] +
                velocity[1] * velocity[1] +
                velocity[2] * velocity[2]);

            int isCrouch = 0;
            if (GetEntProp(g_botIds[i], Prop_Send, "m_fFlags") & FL_DUCKING) {
                isCrouch = 1;
            }

            char botStr[STRING_SIZE];
            Format(botStr, sizeof(botStr), "%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%d",
                position[0], position[1], position[2], g_bots[i].currentAngles[1],
                velocity[0], velocity[1], velocity[2], totalVelocity, isCrouch);
            
            if (i == 0) {
                Format(messageStr, sizeof(messageStr), "%s", botStr);
            } else {
                StrCat(messageStr, sizeof(messageStr), ";");
                StrCat(messageStr, sizeof(messageStr), botStr);
            }
        }

        SendMessage(TICK, messageStr);
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
    if (!g_isStarted)
    {
        return Plugin_Continue;
    }

    int botIndex = -1;
    for (int i = 0; i < g_botCount; i++) {
        if (g_botIds[i] == client) {
            botIndex = i;
            break;
        }
    }

    if (botIndex == -1) {
        return Plugin_Continue;
    }

    buttons = 0;

    vel[0] = 0.0;
    vel[1] = 0.0;
    vel[2] = 0.0;

    int isF = 0;
    GetTrieValue(g_bots[botIndex].buttons, "f", isF);
    if (isF == 1) {
        vel[0] = 100000.0;
    }

    g_bots[botIndex].currentAngles[0] = NormalizeDegree(g_bots[botIndex].currentAngles[0] + g_bots[botIndex].mouseY);
    g_bots[botIndex].currentAngles[1] = NormalizeDegree(g_bots[botIndex].currentAngles[1] + g_bots[botIndex].mouseX);

    angles[0] = g_bots[botIndex].currentAngles[0];
    angles[1] = g_bots[botIndex].currentAngles[1];
    
    TeleportEntity(client, NULL_VECTOR, g_bots[botIndex].currentAngles, NULL_VECTOR);

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
    char separatorStr[2];
    _PrepSepString(str, separator, separatorStr, sepCount);
    ExplodeString(str, separatorStr, sepData, sepCount, STRING_SIZE);
}

void SepStringBig(const char[] str, const char separator, char sepData[MAX_STRING_SEP_BIG][STRING_SIZE_BIG], int &sepCount) {
    char separatorStr[2];
    _PrepSepString(str, separator, separatorStr, sepCount);
    ExplodeString(str, separatorStr, sepData, sepCount, STRING_SIZE_BIG);
}

void _PrepSepString(const char[] str, const char separator, char separatorStr[2], int &sepCount) {
    separatorStr[0] = separator;
    separatorStr[1] = '\0';

    sepCount = 1;
    int strLength = strlen(str);
    for (int i = 0; i < strLength; i++) {
        if (str[i] == separator) {
            sepCount++;
        }
    }
}
