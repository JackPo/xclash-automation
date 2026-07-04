/*
 * Frida script to read memory context around stamina strings
 */

console.log("[*] Reading memory around stamina addresses...");

var addresses = [
    0x41afd063,
    0x41afd29e,
    0x41afdf2e
];

addresses.forEach(function(addr) {
    try {
        var p = ptr(addr);
        console.log("\n=== Address: " + p + " ===");
        console.log(hexdump(p.sub(32), {length: 128, header: true, ansi: false}));
    } catch(e) {
        console.log("Error at 0x" + addr.toString(16) + ": " + e);
    }
});

// Also search for JSON pattern "stamina": followed by number
console.log("\n[*] Searching for stamina JSON patterns in readable memory...");

var modules = Process.enumerateModules();
console.log("[*] Found " + modules.length + " modules");

// Look at monochrome module specifically
var monochrome = null;
modules.forEach(function(m) {
    if (m.name.indexOf("monochrome") !== -1) {
        monochrome = m;
        console.log("[*] Found monochrome at " + m.base + " size: " + m.size);
    }
});

console.log("\n[*] Done.");
