/*
 * Frida script to hook XLua and intercept game data
 * Last War uses Unity + XLua for game logic
 */

console.log("[*] XLua Hook Script");

// Find xlua module
var xluaModule = Process.findModuleByName("libxlua.so");
if (!xluaModule) {
    console.log("[-] libxlua.so not found");
} else {
    console.log("[+] Found libxlua.so at " + xluaModule.base + " size: " + xluaModule.size);

    // List some exports from xlua
    var exports = xluaModule.enumerateExports();
    console.log("[*] Found " + exports.length + " exports in libxlua.so");

    // Look for interesting functions
    var interestingFuncs = [];
    exports.forEach(function(exp) {
        var name = exp.name.toLowerCase();
        if (name.indexOf('lua_get') !== -1 ||
            name.indexOf('lua_set') !== -1 ||
            name.indexOf('lua_push') !== -1 ||
            name.indexOf('luaL_') !== -1) {
            interestingFuncs.push(exp);
        }
    });

    console.log("\n[*] Interesting Lua functions:");
    interestingFuncs.slice(0, 20).forEach(function(f) {
        console.log("  " + f.name + " @ " + f.address);
    });
}

// Find Unity module
var unityModule = Process.findModuleByName("libunity.so");
if (!unityModule) {
    console.log("[-] libunity.so not found");
} else {
    console.log("\n[+] Found libunity.so at " + unityModule.base + " size: " + unityModule.size);
}

// Find data-trans-hub which handles network data
var dataTransModule = Process.findModuleByName("libdata-trans-hub.so");
if (dataTransModule) {
    console.log("\n[+] Found libdata-trans-hub.so at " + dataTransModule.base);

    var exports = dataTransModule.enumerateExports();
    console.log("[*] Found " + exports.length + " exports");

    // Look for send/receive functions
    exports.forEach(function(exp) {
        var name = exp.name.toLowerCase();
        if (name.indexOf('send') !== -1 ||
            name.indexOf('recv') !== -1 ||
            name.indexOf('write') !== -1 ||
            name.indexOf('read') !== -1 ||
            name.indexOf('request') !== -1 ||
            name.indexOf('response') !== -1) {
            console.log("  [NET] " + exp.name + " @ " + exp.address);
        }
    });
}

// Find signer module which might handle encryption
var signerModule = Process.findModuleByName("libsigner.so");
if (signerModule) {
    console.log("\n[+] Found libsigner.so at " + signerModule.base);

    var exports = signerModule.enumerateExports();
    console.log("[*] Found " + exports.length + " exports");

    exports.slice(0, 15).forEach(function(exp) {
        console.log("  " + exp.name + " @ " + exp.address);
    });
}

console.log("\n[*] Module enumeration complete.");
