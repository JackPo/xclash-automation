/*
 * Frida script to intercept WebSocket traffic in Last War: Survival
 * The game uses WebSocket for real-time data (stamina, positions, resources)
 */

console.log("[*] WebSocket Intercept Script Loaded");

// Helper function to convert byte array to string
function byteArrayToString(byteArray) {
    if (!byteArray) return "null";
    try {
        var result = "";
        for (var i = 0; i < byteArray.length; i++) {
            var b = byteArray[i];
            if (b < 0) b += 256;
            if (b >= 32 && b < 127) {
                result += String.fromCharCode(b);
            } else {
                result += ".";
            }
        }
        return result;
    } catch (e) {
        return "[error: " + e + "]";
    }
}

function byteArrayToHex(byteArray) {
    if (!byteArray) return "null";
    try {
        var hex = "";
        for (var i = 0; i < Math.min(byteArray.length, 128); i++) {
            var b = byteArray[i];
            if (b < 0) b += 256;
            hex += ("0" + b.toString(16)).slice(-2) + " ";
        }
        if (byteArray.length > 128) hex += "...";
        return hex;
    } catch (e) {
        return "[error: " + e + "]";
    }
}

Java.perform(function() {
    console.log("[+] Java environment ready");

    // ========================================
    // HOOK 1: OkHttp WebSocket
    // ========================================
    try {
        var RealWebSocket = Java.use('okhttp3.internal.ws.RealWebSocket');

        // Hook send for text messages
        RealWebSocket.send.overload('java.lang.String').implementation = function(text) {
            console.log("\n[WS-SEND-TEXT] ========================================");
            console.log("[WS-SEND-TEXT] Length: " + text.length);
            console.log("[WS-SEND-TEXT] " + text.substring(0, 2000));
            console.log("[WS-SEND-TEXT] ========================================\n");
            return this.send(text);
        };
        console.log("[+] Hooked RealWebSocket.send(String)");

        // Hook send for binary messages
        RealWebSocket.send.overload('okio.ByteString').implementation = function(bytes) {
            var byteArray = bytes.toByteArray();
            console.log("\n[WS-SEND-BIN] ========================================");
            console.log("[WS-SEND-BIN] Length: " + byteArray.length);
            console.log("[WS-SEND-BIN] Hex: " + byteArrayToHex(byteArray));
            console.log("[WS-SEND-BIN] Ascii: " + byteArrayToString(byteArray));
            console.log("[WS-SEND-BIN] ========================================\n");
            return this.send(bytes);
        };
        console.log("[+] Hooked RealWebSocket.send(ByteString)");

    } catch (e) {
        console.log("[-] RealWebSocket error: " + e);
    }

    // ========================================
    // HOOK 2: WebSocket Listener (incoming messages)
    // ========================================
    try {
        var WebSocketListener = Java.use('okhttp3.WebSocketListener');

        WebSocketListener.onMessage.overload('okhttp3.WebSocket', 'java.lang.String').implementation = function(ws, text) {
            console.log("\n[WS-RECV-TEXT] ========================================");
            console.log("[WS-RECV-TEXT] Length: " + text.length);
            console.log("[WS-RECV-TEXT] " + text.substring(0, 2000));
            console.log("[WS-RECV-TEXT] ========================================\n");
            return this.onMessage(ws, text);
        };
        console.log("[+] Hooked WebSocketListener.onMessage(String)");

        WebSocketListener.onMessage.overload('okhttp3.WebSocket', 'okio.ByteString').implementation = function(ws, bytes) {
            var byteArray = bytes.toByteArray();
            console.log("\n[WS-RECV-BIN] ========================================");
            console.log("[WS-RECV-BIN] Length: " + byteArray.length);
            console.log("[WS-RECV-BIN] Hex: " + byteArrayToHex(byteArray));
            console.log("[WS-RECV-BIN] Ascii: " + byteArrayToString(byteArray));
            console.log("[WS-RECV-BIN] ========================================\n");
            return this.onMessage(ws, bytes);
        };
        console.log("[+] Hooked WebSocketListener.onMessage(ByteString)");

    } catch (e) {
        console.log("[-] WebSocketListener error: " + e);
    }

    // ========================================
    // HOOK 3: Java WebSocket API
    // ========================================
    try {
        var JavaWebSocket = Java.use('java.net.http.WebSocket');
        console.log("[+] Found java.net.http.WebSocket (Java 11+)");
    } catch (e) {
        console.log("[-] java.net.http.WebSocket not available (expected on older Android)");
    }

    // ========================================
    // HOOK 4: OutputStream/InputStream for raw sockets
    // ========================================
    try {
        var DataOutputStream = Java.use('java.io.DataOutputStream');

        DataOutputStream.write.overload('[B', 'int', 'int').implementation = function(b, off, len) {
            if (len > 50 && len < 10000) {
                var str = byteArrayToString(b.slice(off, off + len));
                // Filter for interesting data
                if (str.indexOf('{') !== -1 || str.indexOf('stamina') !== -1 ||
                    str.indexOf('gold') !== -1 || str.indexOf('position') !== -1) {
                    console.log("\n[DATAOUT] ========================================");
                    console.log("[DATAOUT] Length: " + len);
                    console.log("[DATAOUT] " + str.substring(0, 1000));
                    console.log("[DATAOUT] ========================================\n");
                }
            }
            return this.write(b, off, len);
        };
        console.log("[+] Hooked DataOutputStream.write");

    } catch (e) {
        console.log("[-] DataOutputStream error: " + e);
    }

    // ========================================
    // HOOK 5: Socket connect (to see endpoints)
    // ========================================
    try {
        var Socket = Java.use('java.net.Socket');

        Socket.connect.overload('java.net.SocketAddress', 'int').implementation = function(endpoint, timeout) {
            console.log("[SOCKET] Connecting to: " + endpoint.toString());
            return this.connect(endpoint, timeout);
        };
        console.log("[+] Hooked Socket.connect");

    } catch (e) {
        console.log("[-] Socket error: " + e);
    }

    // ========================================
    // HOOK 6: SSLSocket for encrypted sockets
    // ========================================
    try {
        var SSLSocketImpl = Java.use('com.android.org.conscrypt.ConscryptFileDescriptorSocket');

        SSLSocketImpl.startHandshake.implementation = function() {
            console.log("[SSL] Handshake starting with: " + this.getInetAddress().toString() + ":" + this.getPort());
            return this.startHandshake();
        };
        console.log("[+] Hooked SSL Handshake");

    } catch (e) {
        console.log("[-] SSLSocket error: " + e);
    }

    // ========================================
    // HOOK 7: BufferedOutputStream (common for network)
    // ========================================
    try {
        var BufferedOutputStream = Java.use('java.io.BufferedOutputStream');

        BufferedOutputStream.write.overload('[B', 'int', 'int').implementation = function(b, off, len) {
            if (len > 100 && len < 5000) {
                var str = byteArrayToString(b.slice(off, off + len));
                if (str.indexOf('{') !== -1 && (str.indexOf('"') !== -1)) {
                    console.log("\n[BUFFOUT] ========================================");
                    console.log("[BUFFOUT] Length: " + len);
                    console.log("[BUFFOUT] " + str.substring(0, 1000));
                    console.log("[BUFFOUT] ========================================\n");
                }
            }
            return this.write(b, off, len);
        };
        console.log("[+] Hooked BufferedOutputStream.write");

    } catch (e) {
        console.log("[-] BufferedOutputStream error: " + e);
    }

    console.log("\n[*] WebSocket hooks installed. Monitoring...\n");
});
