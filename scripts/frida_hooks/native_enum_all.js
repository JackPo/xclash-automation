/*
 * Frida script to list ALL native modules
 */

console.log("[*] Listing ALL loaded modules:\n");

var modules = Process.enumerateModules();
console.log("Total modules: " + modules.length + "\n");

modules.forEach(function(module) {
    console.log(module.name.padEnd(50) + " @ " + module.base + " (" + (module.size/1024/1024).toFixed(2) + " MB)");
});

console.log("\n[*] Done. Looking for Unity/game modules specifically...\n");

// Search for anything game-related
modules.forEach(function(module) {
    var name = module.name.toLowerCase();
    if (name.indexOf('unity') !== -1 ||
        name.indexOf('il2cpp') !== -1 ||
        name.indexOf('xman') !== -1 ||
        name.indexOf('xclash') !== -1 ||
        name.indexOf('q1') !== -1 ||
        name.indexOf('lua') !== -1 ||
        name.indexOf('game') !== -1) {
        console.log("[GAME] " + module.name + " @ " + module.base + " (" + (module.size/1024/1024).toFixed(2) + " MB)");
    }
});
