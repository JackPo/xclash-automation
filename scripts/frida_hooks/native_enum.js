/*
 * Frida script to enumerate native modules and find encryption functions
 */

console.log("[*] Native Module Enumeration Script");

// List all loaded modules
var modules = Process.enumerateModules();
console.log("\n[*] Loaded modules (" + modules.length + " total):\n");

modules.forEach(function(module) {
    if (module.name.indexOf('libdata') !== -1 ||
        module.name.indexOf('libil2cpp') !== -1 ||
        module.name.indexOf('libxlua') !== -1 ||
        module.name.indexOf('libq1') !== -1 ||
        module.name.indexOf('crypto') !== -1 ||
        module.name.indexOf('ssl') !== -1) {
        console.log("  " + module.name + " @ " + module.base + " (" + module.size + " bytes)");
    }
});

// Find libdata-trans-hub.so
var dataTransHub = Process.findModuleByName('libdata-trans-hub.so');
if (dataTransHub) {
    console.log("\n[+] Found libdata-trans-hub.so at " + dataTransHub.base);
    console.log("[*] Enumerating exports...\n");

    var exports = dataTransHub.enumerateExports();
    exports.forEach(function(exp) {
        console.log("  " + exp.type + " " + exp.name + " @ " + exp.address);
    });
}

// Find libil2cpp.so encryption-related exports
var il2cpp = Process.findModuleByName('libil2cpp.so');
if (il2cpp) {
    console.log("\n[+] Found libil2cpp.so at " + il2cpp.base + " (" + il2cpp.size + " bytes)");
    console.log("[*] Searching for crypto-related symbols...\n");

    var exports = il2cpp.enumerateExports();
    var cryptoExports = [];
    exports.forEach(function(exp) {
        var name = exp.name.toLowerCase();
        if (name.indexOf('encrypt') !== -1 ||
            name.indexOf('decrypt') !== -1 ||
            name.indexOf('cipher') !== -1 ||
            name.indexOf('aes') !== -1 ||
            name.indexOf('crypto') !== -1) {
            cryptoExports.push(exp);
        }
    });

    console.log("[*] Found " + cryptoExports.length + " crypto-related exports:");
    cryptoExports.forEach(function(exp) {
        console.log("  " + exp.type + " " + exp.name + " @ " + exp.address);
    });
}

// Find libq1mmkv.so (key storage)
var q1mmkv = Process.findModuleByName('libq1mmkv.so');
if (q1mmkv) {
    console.log("\n[+] Found libq1mmkv.so at " + q1mmkv.base);
    console.log("[*] Enumerating exports (key storage)...\n");

    var exports = q1mmkv.enumerateExports();
    exports.forEach(function(exp) {
        if (exp.name.indexOf('get') !== -1 || exp.name.indexOf('set') !== -1 ||
            exp.name.indexOf('key') !== -1 || exp.name.indexOf('Key') !== -1) {
            console.log("  " + exp.type + " " + exp.name + " @ " + exp.address);
        }
    });
}

// Find libxlua.so
var xlua = Process.findModuleByName('libxlua.so');
if (xlua) {
    console.log("\n[+] Found libxlua.so at " + xlua.base);
    console.log("[*] Searching for relevant exports...\n");

    var exports = xlua.enumerateExports();
    var relevantExports = [];
    exports.forEach(function(exp) {
        var name = exp.name.toLowerCase();
        if (name.indexOf('call') !== -1 ||
            name.indexOf('pcall') !== -1 ||
            name.indexOf('load') !== -1) {
            relevantExports.push(exp);
        }
    });

    console.log("[*] Found " + relevantExports.length + " call-related exports:");
    relevantExports.forEach(function(exp) {
        console.log("  " + exp.type + " " + exp.name + " @ " + exp.address);
    });
}

console.log("\n[*] Enumeration complete.");
