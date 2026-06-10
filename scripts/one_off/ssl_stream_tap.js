/**
 * Tap plaintext from Conscrypt SSLInputStream/SSLOutputStream.
 */
Java.perform(function () {
  function bytesToAscii(b, off, len) {
    try {
      var out = "";
      var max = Math.min(len, 512);
      for (var i = 0; i < max; i++) {
        var c = b[off + i] & 0xff;
        if (c >= 0x20 && c <= 0x7e) out += String.fromCharCode(c);
        else out += ".";
      }
      return out;
    } catch (e) { return ""; }
  }

  function bytesToHex(b, off, len) {
    try {
      var out = "";
      var max = Math.min(len, 512);
      for (var i = 0; i < max; i++) {
        var c = b[off + i] & 0xff;
        var h = c.toString(16);
        if (h.length === 1) h = "0" + h;
        out += h;
      }
      return out;
    } catch (e) { return ""; }
  }

  function bytesToB64(b, off, len) {
    try {
      var max = Math.min(len, 8192);
      var arr = Java.array('byte', b);
      var slice = Java.use('java.util.Arrays').copyOfRange(arr, off, off + max);
      var Base64 = Java.use('android.util.Base64');
      return Base64.encodeToString(slice, 2); // NO_WRAP
    } catch (e) { return ""; }
  }

  function hookStream(className, dir) {
    try {
      var Cls = Java.use(className);
      if (dir === "in") {
        // read(byte[], int, int)
        if (Cls.read && Cls.read.overload("[B", "int", "int")) {
          Cls.read.overload("[B", "int", "int").implementation = function (b, off, len) {
            var n = this.read(b, off, len);
            if (n > 0) {
              var ascii = bytesToAscii(b, off, n);
              var hex = bytesToHex(b, off, n);
              var b64 = bytesToB64(b, off, n);
              console.log("[SSL READ] " + className + " len=" + n + " ascii=" + ascii);
              console.log("[SSL READ HEX] " + hex);
              if (b64) console.log("[SSL READ B64] " + b64);
            }
            return n;
          };
        }
      } else {
        // write(byte[], int, int)
        if (Cls.write && Cls.write.overload("[B", "int", "int")) {
          Cls.write.overload("[B", "int", "int").implementation = function (b, off, len) {
            var ascii = bytesToAscii(b, off, len);
            var hex = bytesToHex(b, off, len);
            var b64 = bytesToB64(b, off, len);
            console.log("[SSL WRITE] " + className + " len=" + len + " ascii=" + ascii);
            console.log("[SSL WRITE HEX] " + hex);
            if (b64) console.log("[SSL WRITE B64] " + b64);
            return this.write(b, off, len);
          };
        }
      }
      console.log("[*] Hooked " + className + " (" + dir + ")");
    } catch (e) {
      // ignore
    }
  }

  // Conscrypt sockets
  hookStream("com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLInputStream", "in");
  hookStream("com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLOutputStream", "out");
  hookStream("com.android.org.conscrypt.ConscryptEngineSocket$SSLInputStream", "in");
  hookStream("com.android.org.conscrypt.ConscryptEngineSocket$SSLOutputStream", "out");

  console.log("[*] SSL stream tap ready");
});
