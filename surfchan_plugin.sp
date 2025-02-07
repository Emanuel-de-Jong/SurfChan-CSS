#include <sourcemod>
#include <socket>
 
public Plugin myinfo =
{
	name = "surfchan_Plugin",
};

#pragma newdecls required
#pragma semicolon 1

public void OnPluginStart() {
	Socket socket = new Socket(SOCKET_TCP, OnSocketError);
	File hFile = OpenFile("dl.htm", "wb");
	socket.SetArg(hFile);
	socket.Connect(OnSocketConnected, OnSocketReceive, OnSocketDisconnected, "127.0.0.1", 27015);
}

public void OnSocketConnected(Socket socket, any arg) {
	char requestStr[100];
	FormatEx(
		requestStr,
		sizeof(requestStr),
		"Hello from CSS\n"
	);
	socket.Send(requestStr);
}

public void OnSocketReceive(Socket socket, char[] receiveData, const int dataSize, any hFile) {
    PrintToServer(receiveData);
}

public void OnSocketDisconnected(Socket socket, any hFile) {
	CloseHandle(hFile);
	CloseHandle(socket);
}

public void OnSocketError(Socket socket, const int errorType, const int errorNum, any hFile) {
	LogError("socket error %d (errno %d)", errorType, errorNum);
	CloseHandle(hFile);
	CloseHandle(socket);
}
