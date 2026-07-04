/*
 * Frida script to intercept encryption/decryption in Last War: Survival
 * Target: com.xman.na.gp
 *
 * Usage: frida -U -f com.xman.na.gp -l crypto_intercept.js --no-pause
 *    or: frida -U com.xman.na.gp -l crypto_intercept.js
 */

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
        return "[error converting: " + e + "]";
    }
}

// Helper to convert byte array to hex
function byteArrayToHex(byteArray) {
    if (!byteArray) return "null";
    try {
        var hex = "";
        for (var i = 0; i < Math.min(byteArray.length, 64); i++) {
            var b = byteArray[i];
            if (b < 0) b += 256;
            hex += ("0" + b.toString(16)).slice(-2);
        }
        if (byteArray.length > 64) hex += "...";
        return hex;
    } catch (e) {
        return "[error: " + e + "]";
    }
}

// Helper to try parsing as JSON
function tryParseJSON(str) {
    try {
        if (str && str.charAt(0) === '{' || str.charAt(0) === '[') {
            return JSON.stringify(JSON.parse(str), null, 2);
        }
    } catch (e) {}
    return str;
}

console.log("[*] Crypto Intercept Script Loaded");
console.log("[*] Waiting for Java environment...");

Java.perform(function() {
    console.log("[+] Java environment ready");

    // ========================================
    // HOOK 1: javax.crypto.Cipher
    // ========================================
    try {
        var Cipher = Java.use('javax.crypto.Cipher');
        console.log("[+] Found javax.crypto.Cipher");

        // Hook doFinal(byte[])
        Cipher.doFinal.overload('[B').implementation = function(input) {
            var mode = this.getOpmode();  // 1 = ENCRYPT, 2 = DECRYPT
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "UNKNOWN";
            var algo = this.getAlgorithm();

            console.log("\n[CIPHER] ========================================");
            console.log("[CIPHER] Algorithm: " + algo);
            console.log("[CIPHER] Mode: " + modeStr);
            console.log("[CIPHER] Input length: " + (input ? input.length : 0));

            if (input && input.length < 2000) {
                var inputStr = byteArrayToString(input);
                console.log("[CIPHER] Input (ascii): " + inputStr.substring(0, 500));

                // Check if it looks like JSON
                if (inputStr.indexOf('{') !== -1 || inputStr.indexOf('[') !== -1) {
                    console.log("[CIPHER] >>> POTENTIAL JSON DETECTED <<<");
                    console.log(tryParseJSON(inputStr));
                }
            }

            var result = this.doFinal(input);

            if (result && result.length < 2000) {
                var resultStr = byteArrayToString(result);
                console.log("[CIPHER] Output length: " + result.length);
                console.log("[CIPHER] Output (ascii): " + resultStr.substring(0, 500));

                if (resultStr.indexOf('{') !== -1 || resultStr.indexOf('[') !== -1) {
                    console.log("[CIPHER] >>> DECRYPTED JSON <<<");
                    console.log(tryParseJSON(resultStr));
                }
            }
            console.log("[CIPHER] ========================================\n");

            return result;
        };
        console.log("[+] Hooked Cipher.doFinal([B)");

        // Hook doFinal(byte[], int, int)
        Cipher.doFinal.overload('[B', 'int', 'int').implementation = function(input, offset, len) {
            var mode = this.getOpmode();
            var modeStr = (mode === 1) ? "ENCRYPT" : (mode === 2) ? "DECRYPT" : "UNKNOWN";

            console.log("\n[CIPHER2] Mode: " + modeStr + ", Algo: " + this.getAlgorithm());
            console.log("[CIPHER2] Input: offset=" + offset + ", len=" + len);

            if (input && len < 2000) {
                var slice = Java.array('byte', input).slice(offset, offset + len);
                console.log("[CIPHER2] Data: " + byteArrayToString(slice));
            }

            return this.doFinal(input, offset, len);
        };
        console.log("[+] Hooked Cipher.doFinal([B, int, int)");

    } catch (e) {
        console.log("[-] Error hooking Cipher: " + e);
    }

    // ========================================
    // HOOK 2: android.util.Base64
    // ========================================
    try {
        var Base64 = Java.use('android.util.Base64');
        console.log("[+] Found android.util.Base64");

        // Hook encodeToString
        Base64.encodeToString.overload('[B', 'int').implementation = function(input, flags) {
            if (input && input.length > 50 && input.length < 5000) {
                var inputStr = byteArrayToString(input);
                console.log("\n[BASE64-ENC] ========================================");
                console.log("[BASE64-ENC] Input length: " + input.length);
                console.log("[BASE64-ENC] Input: " + inputStr.substring(0, 500));

                if (inputStr.indexOf('{') !== -1) {
                    console.log("[BASE64-ENC] >>> JSON BEFORE ENCODING <<<");
                    console.log(tryParseJSON(inputStr));
                }
                console.log("[BASE64-ENC] ========================================\n");
            }
            return this.encodeToString(input, flags);
        };
        console.log("[+] Hooked Base64.encodeToString");

        // Hook decode
        Base64.decode.overload('java.lang.String', 'int').implementation = function(str, flags) {
            var result = this.decode(str, flags);

            if (result && result.length > 50 && result.length < 5000) {
                var resultStr = byteArrayToString(result);
                console.log("\n[BASE64-DEC] ========================================");
                console.log("[BASE64-DEC] Decoded length: " + result.length);
                console.log("[BASE64-DEC] Decoded: " + resultStr.substring(0, 500));

                if (resultStr.indexOf('{') !== -1) {
                    console.log("[BASE64-DEC] >>> DECODED JSON <<<");
                    console.log(tryParseJSON(resultStr));
                }
                console.log("[BASE64-DEC] ========================================\n");
            }
            return result;
        };
        console.log("[+] Hooked Base64.decode");

    } catch (e) {
        console.log("[-] Error hooking Base64: " + e);
    }

    // ========================================
    // HOOK 3: SecretKeySpec (to capture keys)
    // ========================================
    try {
        var SecretKeySpec = Java.use('javax.crypto.spec.SecretKeySpec');

        SecretKeySpec.$init.overload('[B', 'java.lang.String').implementation = function(key, algo) {
            console.log("\n[KEY] ========================================");
            console.log("[KEY] Algorithm: " + algo);
            console.log("[KEY] Key (hex): " + byteArrayToHex(key));
            console.log("[KEY] Key length: " + key.length + " bytes");
            console.log("[KEY] ========================================\n");
            return this.$init(key, algo);
        };
        console.log("[+] Hooked SecretKeySpec");

    } catch (e) {
        console.log("[-] Error hooking SecretKeySpec: " + e);
    }

    // ========================================
    // HOOK 4: IvParameterSpec (to capture IVs)
    // ========================================
    try {
        var IvParameterSpec = Java.use('javax.crypto.spec.IvParameterSpec');

        IvParameterSpec.$init.overload('[B').implementation = function(iv) {
            console.log("[IV] IV (hex): " + byteArrayToHex(iv) + " (" + iv.length + " bytes)");
            return this.$init(iv);
        };
        console.log("[+] Hooked IvParameterSpec");

    } catch (e) {
        console.log("[-] Error hooking IvParameterSpec: " + e);
    }

    // ========================================
    // HOOK 5: String operations for JSON
    // ========================================
    try {
        var String = Java.use('java.lang.String');

        // Hook getBytes for large strings that look like JSON
        String.getBytes.overload('java.lang.String').implementation = function(charset) {
            var str = this.toString();
            if (str.length > 100 && str.length < 3000) {
                if (str.indexOf('"stamina"') !== -1 ||
                    str.indexOf('"gold"') !== -1 ||
                    str.indexOf('"position"') !== -1 ||
                    str.indexOf('"resource"') !== -1 ||
                    str.indexOf('"player"') !== -1) {
                    console.log("\n[STRING] ========================================");
                    console.log("[STRING] Found game data string!");
                    console.log(str.substring(0, 1000));
                    console.log("[STRING] ========================================\n");
                }
            }
            return this.getBytes(charset);
        };
        console.log("[+] Hooked String.getBytes (looking for game data)");

    } catch (e) {
        console.log("[-] Error hooking String: " + e);
    }

    console.log("\n[*] All hooks installed. Waiting for crypto operations...");
    console.log("[*] Trigger game actions to see encrypted data.\n");
});
