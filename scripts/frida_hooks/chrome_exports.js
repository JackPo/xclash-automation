/*
 * Check exports from libmonochrome.so
 */

console.log("[*] Chrome Exports Check");

var monochrome = Process.findModuleByName("libmonochrome.so");
if (monochrome) {
    console.log("[+] Found libmonochrome.so");

    var exports = monochrome.enumerateExports();
    console.log("[*] Total exports: " + exports.length);

    // Print first 30 exports
    console.log("\n[*] First 30 exports:");
    exports.slice(0, 30).forEach(function(exp) {
        console.log("  " + exp.name);
    });

    // Search for interesting exports
    var interesting = [];
    exports.forEach(function(exp) {
        var name = exp.name.toLowerCase();
        if (name.indexOf('send') !== -1 ||
            name.indexOf('recv') !== -1 ||
            name.indexOf('socket') !== -1 ||
            name.indexOf('ssl') !== -1 ||
            name.indexOf('crypto') !== -1 ||
            name.indexOf('json') !== -1 ||
            name.indexOf('message') !== -1) {
            interesting.push(exp);
        }
    });

    console.log("\n[*] Interesting exports (" + interesting.length + "):");
    interesting.slice(0, 40).forEach(function(exp) {
        console.log("  " + exp.name + " @ " + exp.address);
    });
}

console.log("\n[*] Done.");
