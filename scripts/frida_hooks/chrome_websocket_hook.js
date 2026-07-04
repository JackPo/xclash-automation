/*
 * Hook WebSocket traffic in libmonochrome.so (Chromium)
 */

console.log("[*] Chrome WebSocket Hook");

// Find monochrome module
var monochrome = Process.findModuleByName("libmonochrome.so");
if (!monochrome) {
    console.log("[-] libmonochrome.so not found");
} else {
    console.log("[+] Found libmonochrome.so at " + monochrome.base + " (size: " + (monochrome.size/1024/1024).toFixed(0) + " MB)");

    // WebSocket uses these patterns in Chromium
    // Look for WebSocket frame handling functions
    console.log("\n[*] Searching for WebSocket symbols...");

    var symbols = monochrome.enumerateSymbols();
    console.log("[*] Total symbols: " + symbols.length);

    var wsSymbols = [];
    symbols.forEach(function(sym) {
        var name = sym.name.toLowerCase();
        if (name.indexOf('websocket') !== -1 ||
            name.indexOf('wsmessage') !== -1 ||
            name.indexOf('wsframe') !== -1) {
            wsSymbols.push(sym);
        }
    });

    console.log("[*] Found " + wsSymbols.length + " WebSocket-related symbols:");
    wsSymbols.slice(0, 30).forEach(function(sym) {
        console.log("  " + sym.name + " @ " + sym.address);
    });

    // Also look for BoringSSL functions we could hook
    console.log("\n[*] Searching for SSL functions...");
    var sslSymbols = [];
    symbols.forEach(function(sym) {
        var name = sym.name;
        if (name.indexOf('SSL_read') !== -1 ||
            name.indexOf('SSL_write') !== -1 ||
            name.indexOf('SSL_CTX') !== -1) {
            sslSymbols.push(sym);
        }
    });

    console.log("[*] Found " + sslSymbols.length + " SSL symbols:");
    sslSymbols.slice(0, 20).forEach(function(sym) {
        console.log("  " + sym.name + " @ " + sym.address);
    });
}

console.log("\n[*] Done.");
