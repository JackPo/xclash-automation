/*
 * List all loaded modules to find Unity and XLua
 */

console.log("[*] Enumerating all modules...\n");

var modules = Process.enumerateModules();
console.log("[*] Total modules: " + modules.length + "\n");

// Find game-related modules
modules.forEach(function(m) {
    var name = m.name.toLowerCase();
    if (name.indexOf('unity') !== -1 ||
        name.indexOf('lua') !== -1 ||
        name.indexOf('data') !== -1 ||
        name.indexOf('sign') !== -1 ||
        name.indexOf('xman') !== -1 ||
        name.indexOf('il2cpp') !== -1 ||
        name.indexOf('mono') !== -1 ||
        name.indexOf('q1') !== -1 ||
        name.indexOf('burst') !== -1 ||
        name.indexOf('ssl') !== -1) {
        console.log(m.name + " @ " + m.base + " (size: " + (m.size/1024/1024).toFixed(2) + " MB)");
    }
});

// Also check for the data-trans module
console.log("\n[*] Searching for data transport module...");
modules.forEach(function(m) {
    if (m.name.indexOf('trans') !== -1 || m.name.indexOf('hub') !== -1) {
        console.log(m.name + " @ " + m.base);
    }
});

console.log("\n[*] Done.");
