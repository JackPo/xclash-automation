/**
 * WebSocket tap (pre-TLS) for OkHttp (standard + Q1 namespace).
 * Logs text + binary frames to stdout for capture.
 */
Java.perform(function () {
  function logMsg(prefix, msg) {
    try {
      console.log(prefix + " " + msg);
    } catch (e) {}
  }

  function safeStr(obj) {
    try {
      return obj ? obj.toString() : "";
    } catch (e) {
      return "";
    }
  }

  function hookPackage(pkg) {
    try {
      var WS = Java.use(pkg + ".WebSocket");
      if (WS && WS.send) {
        // send(String)
        if (WS.send.overload("java.lang.String")) {
          WS.send.overload("java.lang.String").implementation = function (text) {
            logMsg("[WS SEND TEXT]", safeStr(text));
            return this.send(text);
          };
        }
        // send(ByteString)
        try {
          WS.send.overload("okio.ByteString").implementation = function (bs) {
            var out = "";
            try { out = bs.utf8(); } catch (e) {}
            if (!out) {
              try { out = bs.hex(); } catch (e2) {}
            }
            logMsg("[WS SEND BIN]", out);
            return this.send(bs);
          };
        } catch (e) {}
        logMsg("[*] Hooked " + pkg + ".WebSocket.send", "");
      }
    } catch (e) {}

    try {
      var WSL = Java.use(pkg + ".WebSocketListener");
      if (WSL && WSL.onMessage) {
        // onMessage(WebSocket, String)
        try {
          WSL.onMessage.overload(pkg + ".WebSocket", "java.lang.String").implementation = function (ws, text) {
            logMsg("[WS RECV TEXT]", safeStr(text));
            return this.onMessage(ws, text);
          };
        } catch (e) {}
        // onMessage(WebSocket, ByteString)
        try {
          WSL.onMessage.overload(pkg + ".WebSocket", "okio.ByteString").implementation = function (ws, bs) {
            var out = "";
            try { out = bs.utf8(); } catch (e) {}
            if (!out) {
              try { out = bs.hex(); } catch (e2) {}
            }
            logMsg("[WS RECV BIN]", out);
            return this.onMessage(ws, bs);
          };
        } catch (e) {}
        logMsg("[*] Hooked " + pkg + ".WebSocketListener.onMessage", "");
      }
    } catch (e) {}

    // Log OkHttp newWebSocket usage
    try {
      var OkHttpClient = Java.use(pkg + ".OkHttpClient");
      if (OkHttpClient && OkHttpClient.newWebSocket) {
        OkHttpClient.newWebSocket.implementation = function (req, listener) {
          var url = "";
          try { url = req.url().toString(); } catch (e) {}
          logMsg("[WS NEW]", pkg + " url=" + url);
          return this.newWebSocket(req, listener);
        };
        logMsg("[*] Hooked " + pkg + ".OkHttpClient.newWebSocket", "");
      }
    } catch (e) {}

    // Hook internal RealWebSocket (okhttp)
    try {
      var RealWS = Java.use(pkg + ".internal.ws.RealWebSocket");
      try {
        // constructor to log URL
        RealWS.$init.overload(pkg + ".Request", pkg + ".WebSocketListener", "java.util.Random", "long").implementation = function (req, listener, rand, ping) {
          var url = "";
          try { url = req.url().toString(); } catch (e) {}
          logMsg("[RWS INIT]", pkg + " url=" + url);
          return this.$init(req, listener, rand, ping);
        };
      } catch (e) {}
      // text frames
      if (RealWS.onReadMessage && RealWS.onReadMessage.overload("java.lang.String")) {
        RealWS.onReadMessage.overload("java.lang.String").implementation = function (text) {
          logMsg("[RWS RECV TEXT]", safeStr(text));
          return this.onReadMessage(text);
        };
      }
      // binary frames
      try {
        RealWS.onReadMessage.overload("okio.ByteString").implementation = function (bs) {
          var out = "";
          try { out = bs.utf8(); } catch (e) {}
          if (!out) {
            try { out = bs.hex(); } catch (e2) {}
          }
          logMsg("[RWS RECV BIN]", out);
          return this.onReadMessage(bs);
        };
      } catch (e) {}
      // send text
      if (RealWS.send && RealWS.send.overload("java.lang.String")) {
        RealWS.send.overload("java.lang.String").implementation = function (text) {
          logMsg("[RWS SEND TEXT]", safeStr(text));
          return this.send(text);
        };
      }
      // send binary
      try {
        RealWS.send.overload("okio.ByteString").implementation = function (bs) {
          var out = "";
          try { out = bs.utf8(); } catch (e) {}
          if (!out) {
            try { out = bs.hex(); } catch (e2) {}
          }
          logMsg("[RWS SEND BIN]", out);
          return this.send(bs);
        };
      } catch (e) {}
      logMsg("[*] Hooked " + pkg + ".internal.ws.RealWebSocket", "");
    } catch (e) {}
  }

  hookPackage("okhttp3");
  hookPackage("com.q1.common.lib.okhttp3");

  logMsg("[*] WS tap ready", "");
});
