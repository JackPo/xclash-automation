/**
 * Native socket tap: track connections and dump send/recv.
 * Also hook mbedtls_ssl_read/write and SSL_read/write if present.
 */

const CHAT_IP = ""; // set to specific IP to filter
const LOG_PORTS = new Set([80, 443, 8080, 8443, 5222, 5223, 5228]);
const MAX_ASCII = 256;
const MAX_HEX = 96;

const fdPeer = new Map(); // fd -> { ip, port, family }

function ntohs(x) {
  return ((x & 0xff) << 8) | ((x >> 8) & 0xff);
}

function bytesToAscii(ptr, len) {
  try {
    const bytes = Memory.readByteArray(ptr, len);
    if (!bytes) return "";
    const u8 = new Uint8Array(bytes);
    let out = "";
    const max = Math.min(u8.length, MAX_ASCII);
    for (let i = 0; i < max; i++) {
      const c = u8[i];
      if (c >= 0x20 && c <= 0x7e) out += String.fromCharCode(c);
      else out += ".";
    }
    return out;
  } catch (e) { return "<err>"; }
}

function bytesToHex(ptr, len) {
  try {
    const bytes = Memory.readByteArray(ptr, len);
    if (!bytes) return "";
    const u8 = new Uint8Array(bytes);
    const max = Math.min(u8.length, MAX_HEX);
    let out = "";
    for (let i = 0; i < max; i++) {
      const b = u8[i].toString(16).padStart(2, "0");
      out += b;
    }
    return out;
  } catch (e) { return "<err>"; }
}

function formatIpv6(u8) {
  const parts = [];
  for (let i = 0; i < 16; i += 2) {
    const part = (u8[i] << 8) | u8[i + 1];
    parts.push(part.toString(16));
  }
  return parts.join(":");
}

function parseSockaddr(saPtr) {
  try {
    if (!saPtr) return null;
    if (saPtr.isNull && saPtr.isNull()) return null;
    const family = Memory.readU16(saPtr);
    if (family === 2) { // AF_INET
      const port = ntohs(Memory.readU16(saPtr.add(2)));
      const b0 = Memory.readU8(saPtr.add(4));
      const b1 = Memory.readU8(saPtr.add(5));
      const b2 = Memory.readU8(saPtr.add(6));
      const b3 = Memory.readU8(saPtr.add(7));
      return { family, ip: `${b0}.${b1}.${b2}.${b3}`, port };
    }
    if (family === 10) { // AF_INET6
      const port = ntohs(Memory.readU16(saPtr.add(2)));
      const bytes = [];
      for (let i = 0; i < 16; i++) bytes.push(Memory.readU8(saPtr.add(8 + i)));
      return { family, ip: formatIpv6(bytes), port };
    }
  } catch (e) {}
  return null;
}

function shouldLogPeer(peer) {
  if (!peer) return false;
  if (!CHAT_IP) return true;
  return peer.ip === CHAT_IP;
}

function shouldLogData(peer) {
  if (!peer) return false;
  if (CHAT_IP && peer.ip !== CHAT_IP) return false;
  if (!LOG_PORTS || LOG_PORTS.size === 0) return true;
  return LOG_PORTS.has(peer.port);
}


function hookConnect() {
  const findExport = (name, moduleName) => {
    try {
      if (Module && typeof Module.findGlobalExportByName === "function") {
        return Module.findGlobalExportByName(name);
      }
      if (Module && typeof Module.findExportByName === "function") {
        return Module.findExportByName(moduleName || null, name);
      }
      if (Module && typeof Module.getExportByName === "function") {
        return Module.getExportByName(moduleName || null, name);
      }
    } catch (e) { return null; }
    return null;
  };

  if (!findExport) {
    console.log("[*] Module export lookup not available");
    return;
  }

  const connectPtr = findExport("connect") || findExport("connect", "libc.so");
  if (!connectPtr) {
    console.log("[*] connect not found");
    return;
  }
  Interceptor.attach(connectPtr, {
    onEnter(args) {
      this.fd = args[0].toInt32();
      this.sa = args[1];
    },
    onLeave(retval) {
      if (retval.toInt32() !== 0) return;
      const peer = parseSockaddr(this.sa);
      if (peer) {
        fdPeer.set(this.fd, peer);
        if (shouldLogPeer(peer)) {
          console.log("[CONNECT] fd=" + this.fd + " -> " + peer.ip + ":" + peer.port);
        }
      }
    }
  });
}

function hookSendRecv() {
  const findExport = (name, moduleName) => {
    try {
      if (Module && typeof Module.findGlobalExportByName === "function") {
        return Module.findGlobalExportByName(name);
      }
      if (Module && typeof Module.findExportByName === "function") {
        return Module.findExportByName(moduleName || null, name);
      }
      if (Module && typeof Module.getExportByName === "function") {
        return Module.getExportByName(moduleName || null, name);
      }
    } catch (e) { return null; }
    return null;
  };

  if (!findExport) {
    console.log("[*] Module export lookup not available");
    return;
  }

  const sendPtr = findExport("send") || findExport("send", "libc.so");
  const recvPtr = findExport("recv") || findExport("recv", "libc.so");
  const sendtoPtr = findExport("sendto") || findExport("sendto", "libc.so");
  const recvfromPtr = findExport("recvfrom") || findExport("recvfrom", "libc.so");
  const closePtr = findExport("close") || findExport("close", "libc.so");
  const writePtr = findExport("write") || findExport("write", "libc.so");
  const readPtr = findExport("read") || findExport("read", "libc.so");
  const writevPtr = findExport("writev") || findExport("writev", "libc.so");
  const readvPtr = findExport("readv") || findExport("readv", "libc.so");
  const sendmsgPtr = findExport("sendmsg") || findExport("sendmsg", "libc.so");
  const recvmsgPtr = findExport("recvmsg") || findExport("recvmsg", "libc.so");
  const getpeernamePtr = findExport("getpeername") || findExport("getpeername", "libc.so");
  const getpeernameFn = getpeernamePtr ? new NativeFunction(getpeernamePtr, "int", ["int", "pointer", "pointer"]) : null;

  function getPeerForFd(fd) {
    const cached = fdPeer.get(fd);
    if (cached) return cached;
    if (!getpeernameFn) return null;
    try {
      const addr = Memory.alloc(128);
      const addrlen = Memory.alloc(4);
      Memory.writeU32(addrlen, 128);
      const res = getpeernameFn(fd, addr, addrlen);
      if (res !== 0) return null;
      const peer = parseSockaddr(addr);
      if (peer) fdPeer.set(fd, peer);
      return peer;
    } catch (e) {
      return null;
    }
  }

  if (closePtr) {
    Interceptor.attach(closePtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        fdPeer.delete(fd);
      }
    });
  }

  if (sendPtr) {
    Interceptor.attach(sendPtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        const peer = getPeerForFd(fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        const buf = args[1];
        const len = args[2].toInt32();
        const ascii = bytesToAscii(buf, len);
        const hex = bytesToHex(buf, len);
        console.log("[SEND] fd=" + fd + " " + peer.ip + ":" + peer.port + " len=" + len + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }

  if (recvPtr) {
    Interceptor.attach(recvPtr, {
      onEnter(args) {
        this.fd = args[0].toInt32();
        this.buf = args[1];
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n <= 0) return;
        const peer = getPeerForFd(this.fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        const ascii = bytesToAscii(this.buf, n);
        const hex = bytesToHex(this.buf, n);
        console.log("[RECV] fd=" + this.fd + " " + peer.ip + ":" + peer.port + " len=" + n + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }

  if (writePtr) {
    Interceptor.attach(writePtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        const peer = getPeerForFd(fd);
        const len = args[2].toInt32();
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        const ascii = bytesToAscii(args[1], len);
        const hex = bytesToHex(args[1], len);
        console.log("[WRITE] fd=" + fd + " " + peer.ip + ":" + peer.port + " len=" + len + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }

  if (readPtr) {
    Interceptor.attach(readPtr, {
      onEnter(args) {
        this.fd = args[0].toInt32();
        this.buf = args[1];
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n <= 0) return;
        const peer = getPeerForFd(this.fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        const ascii = bytesToAscii(this.buf, n);
        const hex = bytesToHex(this.buf, n);
        console.log("[READ] fd=" + this.fd + " " + peer.ip + ":" + peer.port + " len=" + n + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }

  if (writevPtr) {
    Interceptor.attach(writevPtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        const peer = getPeerForFd(fd);
        const iovcnt = args[2].toInt32();
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        console.log("[WRITEV] fd=" + fd + " " + peer.ip + ":" + peer.port + " iovcnt=" + iovcnt);
      }
    });
  }

  if (readvPtr) {
    Interceptor.attach(readvPtr, {
      onEnter(args) {
        this.fd = args[0].toInt32();
        this.iovcnt = args[2].toInt32();
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n <= 0) return;
        const peer = getPeerForFd(this.fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        console.log("[READV] fd=" + this.fd + " " + peer.ip + ":" + peer.port + " len=" + n + " iovcnt=" + this.iovcnt);
      }
    });
  }

  if (sendmsgPtr) {
    Interceptor.attach(sendmsgPtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        const peer = getPeerForFd(fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        console.log("[SENDMSG] fd=" + fd + " " + peer.ip + ":" + peer.port);
      }
    });
  }

  if (recvmsgPtr) {
    Interceptor.attach(recvmsgPtr, {
      onEnter(args) {
        this.fd = args[0].toInt32();
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n <= 0) return;
        const peer = getPeerForFd(this.fd);
        if (!peer) return;
        if (!shouldLogData(peer)) return;
        console.log("[RECVMSG] fd=" + this.fd + " " + peer.ip + ":" + peer.port + " len=" + n);
      }
    });
  }

  if (sendtoPtr) {
    Interceptor.attach(sendtoPtr, {
      onEnter(args) {
        const fd = args[0].toInt32();
        const buf = args[1];
        const len = args[2].toInt32();
        const sa = args[4];
        const peer = parseSockaddr(sa);
        if (peer) fdPeer.set(fd, peer);
        if (!shouldLogData(peer)) return;
        const ascii = bytesToAscii(buf, len);
        const hex = bytesToHex(buf, len);
        console.log("[SENDTO] fd=" + fd + " " + peer.ip + ":" + peer.port + " len=" + len + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }

  if (recvfromPtr) {
    Interceptor.attach(recvfromPtr, {
      onEnter(args) {
        this.fd = args[0].toInt32();
        this.buf = args[1];
        this.sa = args[4];
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n <= 0) return;
        const peer = parseSockaddr(this.sa) || fdPeer.get(this.fd);
        if (peer) fdPeer.set(this.fd, peer);
        if (!shouldLogData(peer)) return;
        const ascii = bytesToAscii(this.buf, n);
        const hex = bytesToHex(this.buf, n);
        console.log("[RECVFROM] fd=" + this.fd + " " + peer.ip + ":" + peer.port + " len=" + n + " ascii=" + ascii + " hex=" + hex);
      }
    });
  }
}

function hookMbedTLS() {
  const findExport = (name, moduleName) => {
    try {
      if (Module && typeof Module.findGlobalExportByName === "function") {
        return Module.findGlobalExportByName(name);
      }
      if (Module && typeof Module.findExportByName === "function") {
        return Module.findExportByName(moduleName || null, name);
      }
      if (Module && typeof Module.getExportByName === "function") {
        return Module.getExportByName(moduleName || null, name);
      }
    } catch (e) { return null; }
    return null;
  };

  if (!findExport) return;

  const mbedtlsWrite = findExport("mbedtls_ssl_write");
  const mbedtlsRead = findExport("mbedtls_ssl_read");
  if (mbedtlsWrite) {
    Interceptor.attach(mbedtlsWrite, {
      onEnter(args) {
        const buf = args[1];
        const len = args[2].toInt32();
        const ascii = bytesToAscii(buf, len);
        console.log("[MBEDTLS WRITE] len=" + len + " ascii=" + ascii);
      }
    });
    console.log("[*] Hooked mbedtls_ssl_write");
  }
  if (mbedtlsRead) {
    Interceptor.attach(mbedtlsRead, {
      onEnter(args) {
        this.buf = args[1];
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n > 0) {
          const ascii = bytesToAscii(this.buf, n);
          console.log("[MBEDTLS READ] len=" + n + " ascii=" + ascii);
        }
      }
    });
    console.log("[*] Hooked mbedtls_ssl_read");
  }
}

function hookOpenSSL() {
  const findExport = (name, moduleName) => {
    try {
      if (Module && typeof Module.findGlobalExportByName === "function") {
        return Module.findGlobalExportByName(name);
      }
      if (Module && typeof Module.findExportByName === "function") {
        return Module.findExportByName(moduleName || null, name);
      }
      if (Module && typeof Module.getExportByName === "function") {
        return Module.getExportByName(moduleName || null, name);
      }
    } catch (e) { return null; }
    return null;
  };

  if (!findExport) return;

  const sslWrite = findExport("SSL_write");
  const sslRead = findExport("SSL_read");
  if (sslWrite) {
    Interceptor.attach(sslWrite, {
      onEnter(args) {
        const buf = args[1];
        const len = args[2].toInt32();
        const ascii = bytesToAscii(buf, len);
        console.log("[SSL WRITE] len=" + len + " ascii=" + ascii);
      }
    });
    console.log("[*] Hooked SSL_write");
  }
  if (sslRead) {
    Interceptor.attach(sslRead, {
      onEnter(args) {
        this.buf = args[1];
      },
      onLeave(retval) {
        const n = retval.toInt32();
        if (n > 0) {
          const ascii = bytesToAscii(this.buf, n);
          console.log("[SSL READ] len=" + n + " ascii=" + ascii);
        }
      }
    });
    console.log("[*] Hooked SSL_read");
  }
}

setTimeout(function () {
  hookConnect();
  hookSendRecv();
  hookMbedTLS();
  hookOpenSSL();
  console.log("[*] native_net_tap ready for " + (CHAT_IP || "ALL"));
}, 1000);
