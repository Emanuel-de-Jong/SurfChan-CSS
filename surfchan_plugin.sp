#include <sourcemod>
#include <sdktools>
#include <socket>
#include <sstream>
#include <string>
#include <optional>

enum class MESSAGE_TYPE {
    TEST = 0,
    START = 1,
    TICK = 2,
    MOVE = 3
};

class Message {
public:
    MESSAGE_TYPE type;
    std::string data;

    Message(MESSAGE_TYPE type, const std::string& data)
        : type(type), data(data) {}

    std::string toString() const {
        return std::to_string(static_cast<int>(type)) + ":" + data;
    }

    static std::optional<Message> DecodeMessage(const std::string& messageStr) {
        if (messageStr.empty()) {
            LogError("Empty message received");
            return std::nullopt;
        }

        size_t delimiterPos = messageStr.find(':');
        if (delimiterPos == std::string::npos) {
            LogError("Message has invalid format: %s", messageStr.c_str());
            return std::nullopt;
        }

        std::string typeStr = messageStr.substr(0, delimiterPos);
        std::string dataStr = messageStr.substr(delimiterPos + 1);

        try {
            int messageTypeInt = std::stoi(typeStr);
            return Message(static_cast<MESSAGE_TYPE>(messageTypeInt), dataStr);
        } catch (...) {
            LogError("Invalid message type: %s", typeStr.c_str());
            return std::nullopt;
        }
    }
};

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
    std::string message_str = std::string(receiveData);
    auto message = Message::DecodeMessage(message_str);
    if (!message.has_value()) {
        return;
    }

    if (message->type == MESSAGE_TYPE::TEST) {
        PrintToServer(message->data);
        SendMessage(MESSAGE_TYPE::TEST, "Hello from CSS");
    }
    else if (message->type == MESSAGE_TYPE::START) {
        g_isStarted = true;
    }
    else if (message->type == MESSAGE_TYPE::MOVE) {
        ProcessMovement(message->data);
    }
}

void SendMessage(MESSAGE_TYPE type, const std::string& data) {
    Message message(type, data);
    g_socket.Send(message.toString());
}

void ProcessMovement(const std::string& data) {
    int client = GetAnyPlayer();
    if (client == 0) return;

    if (StrContains(data, "move_forward") != -1) {
        TeleportEntity(client, NULL_VECTOR, NULL_VECTOR, view_as<float>({0.0, 200.0, 0.0}));
    }

    if (StrContains(data, "rotate_right") != -1) {
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
    if (g_isConnected && g_isStarted) {
        g_tickCount++;

        if (g_tickCount == TICKS_PER_MESSAGE) {
            g_tickCount = 0;
            SendMessage(MESSAGE_TYPE::TICK, "");
        }
    }
}
