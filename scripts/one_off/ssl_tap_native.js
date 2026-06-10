/**
 * Native SSL tap (BoringSSL/Conscrypt) to capture plaintext buffers.
 * Hooks SSL_write / SSL_read in libssl.so or libboringssl.so if present.
 */

function bytesToAscii(ptr, len) {
  try {
    var bytes = Memory.readByteArray(ptr, len);
    if (!bytes) return "";
    var u8 = new Uint8Array(bytes);
    var out = "";
    for (var i = 0; i < u8.length; i++) {
      var c = u8[i];
      if (c >= 0x20 && c <= 0x7e) out += String.fromCharCode(c);
      else out += ".";
    }
    return out;
  } catch (e) {
    return "";
  }
}

function bytesToHex(ptr, len) {
  try {
    var bytes = Memory.readByteArray(ptr, len);
    if (!bytes) return "";
    var u8 = new Uint8Array(bytes);
    var out = [];
    for (var i = 0; i < u8.length; i++) {
      var h = u8[i].toString(16).padStart(2, "0");
      out.push(h);
    }
    return out.join("");
  } catch (e) {
    return "";
  }
}

function hookSsl(libName) {
  var sslWrite = Module.findExportByName(libName, "SSL_write");
  var sslRead = Module.findExportByName(libName, "SSL_read");

  if (sslWrite) {
    Interceptor.attach(sslWrite, {
      onEnter: function (args) {
        this.buf = args[1];
        this.len = args[2].toInt32();
        this.previewLen = Math.min(this.len, 512);
        var ascii = bytesToAscii(this.buf, this.previewLen);
        var hex = bytesToHex(this.buf, Math.min(this.len, 128));
        console.log("[SSL_write] len=" + this.len + " ascii=" + ascii);
        console.log("[SSL_write_hex] " + hex);
      }
    });
    console.log("[*] Hooked SSL_write in " + libName);
  }

  if (sslRead) {
    Interceptor.attach(sslRead, {
      onEnter: function (args) {
        this.buf = args[1];
        this.len = args[2].toInt32();
      },
      onLeave: function (retval) {
        var n = retval.toInt32();
        if (n > 0) {
          var previewLen = Math.min(n, 512);
          var ascii = bytesToAscii(this.buf, previewLen);
          var hex = bytesToHex(this.buf, Math.min(n, 128));
          console.log("[SSL_read] len=" + n + " ascii=" + ascii);
          console.log("[SSL_read_hex] " + hex);
        }
      }
    });
    console.log("[*] Hooked SSL_read in " + libName);
  }
}

setTimeout(function () {
  var candidates = ["libssl.so", "libboringssl.so", "libconscrypt.so"];
  for (var i = 0; i < candidates.length; i++) {
    var name = candidates[i];
    try {
      if (Module.findBaseAddress(name)) {
        hookSsl(name);
      } else {
        console.log("[*] Not loaded: " + name);
      }
    } catch (e) {}
  }

  // Dump loaded modules that look like ssl/tls/crypto
  try {
    var mods = Process.enumerateModules();
    for (var j = 0; j < mods.length; j++) {
      var m = mods[j].name.toLowerCase();
      if (m.indexOf("ssl") >= 0 || m.indexOf("tls") >= 0 || m.indexOf("crypto") >= 0 || m.indexOf("boring") >= 0 || m.indexOf("conscrypt") >= 0) {
        console.log("[*] Module: " + mods[j].name);
      }
    }
  } catch (e) {}

  console.log("[*] Native SSL tap ready");
}, 1000);
