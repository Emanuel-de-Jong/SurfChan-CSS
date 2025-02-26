#include <sourcemod>
#include <cstrike>
#include <sdktools>
#include <socket>
#include <vphysics>

public Plugin myinfo = {
    name = "surfchan",
    author = "Anon",
    description = "SurfChan",
    version = "0.1"
};

#define SERVER_HOST "127.0.0.1"
#define SERVER_PORT 27015
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
    STEP = 3,
    RESET = 4
};

enum ACTION_STATE {
    REST = 1,
    WAITING = 2,
    REGISTERED = 3
};

Socket g_socket;
bool g_isConnected = false;
float g_gameSpeed = 1.0;
bool g_isStarted = false;
ACTION_STATE g_actionState = REST;
bool g_shouldRunAI = false;
int g_client = 0;
float g_startAngle = 0.0;
float g_startPos[3];
float g_mouseH = 0.0;
float g_mouseV = 0.0;
float g_currentAngles[3];
Handle g_buttons;
int g_buttonCount = 6;
char g_buttonTypes[6][2] = {"f", "b", "l", "r", "j", "c"};

public void OnPluginStart() {
    g_buttons = CreateTrie();
    ResetButtons(g_buttons);

    HookEvent("player_spawn", OnPlayerSpawn);

    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.SetOption(SocketReceiveBuffer, STRING_SIZE_BIG);
    g_socket.SetOption(SocketSendBuffer, STRING_SIZE_VERY_BIG);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
}

void ResetButtons(Handle& buttons) {
    for (int i = 0; i < g_buttonCount; i++) {
        SetTrieValue(buttons, g_buttonTypes[i], 0);
    }
}

public Action OnPlayerSpawn(Event event, const char[] name, bool dontBroadcast) {
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (IsClientInGame(client))
    {
        g_client = client;
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
    } else if (messageType == STEP) {
        HandleStep(messageData);
    } else if (messageType == RESET) {
        HandleReset();
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
    if (g_isConnected) {
        g_socket.Send(message);
    }
}

void HandleInit(const char[] data) {
    float gameSpeed = StringToFloat(data);
    if (gameSpeed != g_gameSpeed) {
        g_gameSpeed = gameSpeed;
        SetConVarFloat(FindConVar("host_timescale"), g_gameSpeed);
    }

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

    g_startPos[0] = StringToFloat(sepData[0]);
    g_startPos[1] = StringToFloat(sepData[1]);
    g_startPos[2] = StringToFloat(sepData[2]);

    g_startAngle = StringToFloat(sepData[3]);
    g_currentAngles[1] = g_startAngle;

    TeleportEntity(g_client, g_startPos, g_currentAngles, NULL_VECTOR);

    g_isStarted = true;
}

void HandleStep(const char[] data) {
    char sepData[MAX_STRING_SEP_BIG][STRING_SIZE_BIG];
    int sepDataCount;
    SepStringBig(data, ',', sepData, sepDataCount);

    g_shouldRunAI = StringToInt(sepData[0]) == 1;
    if (g_shouldRunAI) {
        g_mouseH = StringToFloat(sepData[2]);
        g_mouseV = StringToFloat(sepData[3]);

        ResetButtons(g_buttons);

        for (int i = 0; i < g_buttonCount; i++) {
            if (StrContains(sepData[1], g_buttonTypes[i]) != -1) {
                SetTrieValue(g_buttons, g_buttonTypes[i], 1);
            }
        }
    }

    g_actionState = WAITING;
}

void HandleReset() {
    g_mouseH = 0.0;
    g_mouseV = 0.0;
    
    ResetButtons(g_buttons);

    g_currentAngles[0] = 0.0;
    g_currentAngles[1] = g_startAngle;
    g_currentAngles[2] = 0.0;

    float velocity[3] = {0.0, 0.0, 0.0};

    TeleportEntity(g_client, g_startPos, g_currentAngles, velocity);
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
    if (!g_isStarted || g_client == 0 || !g_shouldRunAI)
    {
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

    int isB = 0;
    GetTrieValue(g_buttons, "b", isB);
    if (isB == 1) {
        if (isF == 0) {
            vel[0] = -100000.0;
        } else {
            vel[0] = 0.0;
        }
    }

    int isL = 0;
    GetTrieValue(g_buttons, "l", isL);
    if (isL == 1) {
        vel[1] = -100000.0;
    }

    int isR = 0;
    GetTrieValue(g_buttons, "r", isR);
    if (isR == 1) {
        if (isL == 0) {
            vel[1] = 100000.0;
        } else {
            vel[1] = 0.0;
        }
    }
    
    int isJ = 0;
    GetTrieValue(g_buttons, "j", isJ);
    if (isJ == 1) {
        buttons |= IN_JUMP;
    }

    int isC = 0;
    GetTrieValue(g_buttons, "c", isC);
    if (isC == 1) {
        buttons |= IN_DUCK;
    }

    g_currentAngles[0] = NormalizeVertical(g_currentAngles[0] - g_mouseV);
    g_currentAngles[1] = NormalizeHorizontal(g_currentAngles[1] - g_mouseH);

    angles[0] = g_currentAngles[0];
    angles[1] = g_currentAngles[1];
    
    TeleportEntity(client, NULL_VECTOR, g_currentAngles, NULL_VECTOR);

    return Plugin_Changed;
}

float NormalizeHorizontal(float degree) {
    while (degree > 180.0) {
        degree -= 360.0;
    }

    while (degree < -180.0) {
        degree += 360.0;
    }

    return degree;
}

float NormalizeVertical(float degree) {
    if (degree > 85.0) {
        degree = 85.0;
    } else if (degree < -85.0) {
        degree = -85.0;
    }

    return degree;
}

public void OnGameFrame() {
    if (!g_isConnected || !g_isStarted || g_actionState == REST) return;

    if (g_actionState == WAITING) {
        g_actionState = REGISTERED;
        return;
    }
    
    g_actionState = REST;

    float player_pos[3];
    GetEntPropVector(g_client, Prop_Send, "m_vecOrigin", player_pos);

    float velocity[3];
    GetEntPropVector(g_client, Prop_Data, "m_vecVelocity", velocity);

    float totalVelocity = SquareRoot(velocity[0] * velocity[0] +
        velocity[1] * velocity[1] +
        velocity[2] * velocity[2]);

    int isCrouch = 0;
    if (GetEntProp(g_client, Prop_Send, "m_fFlags") & FL_DUCKING) {
        isCrouch = 1;
    }

    char messageStr[STRING_SIZE_VERY_BIG];
    Format(messageStr, sizeof(messageStr), "%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%d",
        player_pos[0], player_pos[1], player_pos[2], g_currentAngles[1],
        velocity[0], velocity[1], velocity[2], totalVelocity, isCrouch);

    SendMessage(STEP, messageStr);
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
