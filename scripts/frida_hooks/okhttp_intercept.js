/*
 * Frida script to intercept OkHttp requests/responses
 * This hooks at the HTTP layer to see what's being sent
 */

console.log("[*] OkHttp Intercept Script Loaded");

Java.perform(function() {
    console.log("[+] Java environment ready");

    // ========================================
    // HOOK: OkHttp3 RealCall
    // ========================================
    try {
        var RealCall = Java.use('okhttp3.RealCall');

        RealCall.execute.implementation = function() {
            var request = this.request();
            console.log("\n[OKHTTP] ========================================");
            console.log("[OKHTTP] URL: " + request.url().toString());
            console.log("[OKHTTP] Method: " + request.method());

            var body = request.body();
            if (body !== null) {
                try {
                    var Buffer = Java.use('okio.Buffer');
                    var buffer = Buffer.$new();
                    body.writeTo(buffer);
                    var bodyStr = buffer.readUtf8();
                    console.log("[OKHTTP] Request Body (" + bodyStr.length + " chars):");
                    console.log(bodyStr.substring(0, 2000));
                } catch (e) {
                    console.log("[OKHTTP] Body read error: " + e);
                }
            }

            var response = this.execute();

            try {
                var respBody = response.peekBody(1024 * 100);  // Peek up to 100KB
                var respStr = respBody.string();
                console.log("[OKHTTP] Response (" + respStr.length + " chars):");
                console.log(respStr.substring(0, 2000));
            } catch (e) {
                console.log("[OKHTTP] Response read error: " + e);
            }
            console.log("[OKHTTP] ========================================\n");

            return response;
        };
        console.log("[+] Hooked RealCall.execute");

    } catch (e) {
        console.log("[-] OkHttp3 RealCall error: " + e);
    }

    // ========================================
    // HOOK: HttpURLConnection
    // ========================================
    try {
        var URL = Java.use('java.net.URL');
        URL.openConnection.overload().implementation = function() {
            console.log("[URL] Opening: " + this.toString());
            return this.openConnection();
        };
        console.log("[+] Hooked URL.openConnection");
    } catch (e) {
        console.log("[-] URL error: " + e);
    }

    // ========================================
    // HOOK: OutputStream.write for request bodies
    // ========================================
    try {
        var OutputStream = Java.use('java.io.OutputStream');
        var ByteArrayOutputStream = Java.use('java.io.ByteArrayOutputStream');

        ByteArrayOutputStream.write.overload('[B', 'int', 'int').implementation = function(b, off, len) {
            if (len > 100 && len < 5000) {
                try {
                    var str = "";
                    for (var i = off; i < off + Math.min(len, 500); i++) {
                        var c = b[i];
                        if (c < 0) c += 256;
                        if (c >= 32 && c < 127) str += String.fromCharCode(c);
                        else str += ".";
                    }
                    if (str.indexOf("{") !== -1 || str.indexOf("http") !== -1) {
                        console.log("[STREAM] Write (" + len + "): " + str);
                    }
                } catch (e) {}
            }
            return this.write(b, off, len);
        };
        console.log("[+] Hooked ByteArrayOutputStream.write");
    } catch (e) {
        console.log("[-] Stream error: " + e);
    }

    // ========================================
    // HOOK: JSONObject creation
    // ========================================
    try {
        var JSONObject = Java.use('org.json.JSONObject');

        JSONObject.$init.overload('java.lang.String').implementation = function(str) {
            if (str && str.length > 50) {
                console.log("\n[JSON] ========================================");
                console.log("[JSON] Parsing JSON (" + str.length + " chars):");
                console.log(str.substring(0, 1000));
                console.log("[JSON] ========================================\n");
            }
            return this.$init(str);
        };
        console.log("[+] Hooked JSONObject");
    } catch (e) {
        console.log("[-] JSONObject error: " + e);
    }

    // ========================================
    // HOOK: Try Unity's WWW/UnityWebRequest
    // ========================================
    // These are in IL2CPP so we'd need native hooks

    console.log("\n[*] HTTP hooks installed. Monitoring network traffic...\n");
});
