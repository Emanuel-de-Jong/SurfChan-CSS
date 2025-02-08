#include <sourcemod>
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

Socket g_socket;
bool g_connected = false;
bool g_sending = false;

public void OnPluginStart() {
    g_socket = new Socket(SOCKET_TCP, OnSocketError);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
    
    HookEvent("player_spawn", OnPlayerSpawn, EventHookMode_PostNoCopy);
}

public void OnSocketConnected(Socket socket, any data) {
    g_connected = true;
    PrintToServer("Connected to AI server.");
}

public void OnSocketDisconnected(Socket socket, any data) {
    g_connected = false;
    PrintToServer("Disconnected from AI server. Reconnecting...");
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
}

public void OnSocketError(Socket socket, const int errorType, const int errorNum, any data) {
    g_connected = false;
    LogError("Socket error %d (errno %d). Reconnecting...", errorType, errorNum);
    g_socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, SERVER_HOST, SERVER_PORT);
}

public void OnSocketReceive(Socket socket, char[] receiveData, const int dataSize, any data) {
    g_sending = false;

    char message_str[64];
    strcopy(message_str, sizeof(message_str), receiveData);
    ProcessMovement(message_str);
}

void ProcessMovement(const char[] command) {
    int client = GetAnyPlayer();
    if (client == 0) return;

    if (StrContains(command, "move_forward") != -1) {
        TeleportEntity(client, NULL_VECTOR, NULL_VECTOR, view_as<float>({0.0, 200.0, 0.0}));
    }
    if (StrContains(command, "rotate_right") != -1) {
        float angles[3];
        GetClientEyeAngles(client, angles);
        angles[1] += 10.0;  // Rotate right by 10 degrees
        TeleportEntity(client, NULL_VECTOR, angles, NULL_VECTOR);
    }
}

int GetAnyPlayer() {
    for (int i = 1; i <= MaxClients; i++) {
        if (IsClientInGame(i) && IsPlayerAlive(i)) {
            return i;
        }
    }
    return 0;
}

public void OnGameFrame() {
    if (g_connected && !g_sending) {
        g_sending = true;
        g_socket.Send("tick_update\n");
    }
}
