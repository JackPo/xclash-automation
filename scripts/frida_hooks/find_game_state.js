/*
 * Frida script to find game state data in memory
 * Looking for patterns common in game state objects
 */

console.log("[*] Searching for game state patterns...");

// Search for common game state patterns
// Resources in Last War are: gold, food, iron, oil, diamonds
var patterns = [
    '"gold":',
    '"food":',
    '"iron":',
    '"oil":',
    '"diamond',
    '"nTili":',     // stamina in Chinese (n prefix = number)
    '"tili"',       // stamina field
    'roleInfo',
    '"curStamina',
    'maxStamina',
    '"energy":'
];

var ranges = Process.enumerateRanges('r--');
console.log("[*] Scanning " + ranges.length + " memory ranges...\n");

var foundAddresses = [];
var maxFinds = 30;

ranges.forEach(function(range) {
    if (foundAddresses.length >= maxFinds) return;
    if (range.size > 50000000 || range.size < 1000) return;

    patterns.forEach(function(pattern) {
        if (foundAddresses.length >= maxFinds) return;

        try {
            var results = Memory.scanSync(range.base, range.size, pattern);
            results.forEach(function(match) {
                if (foundAddresses.length >= maxFinds) return;

                try {
                    var context = Memory.readUtf8String(match.address.sub(50), 300);
                    if (context) {
                        // Filter out URL-encoded chat and JS code
                        if (context.indexOf('%20') === -1 &&
                            context.indexOf('%22') === -1 &&
                            context.indexOf('function') === -1 &&
                            context.indexOf('return') === -1) {
                            console.log("\n[MATCH] Pattern '" + pattern + "' at " + match.address);
                            console.log("[CONTEXT] " + context.replace(/\n/g, ' ').substring(0, 250));
                            foundAddresses.push(match.address);
                        }
                    }
                } catch(e) {}
            });
        } catch(e) {}
    });
});

console.log("\n[*] Found " + foundAddresses.length + " potential game state locations");

// Also try searching for specific role ID which we know: 5179912
console.log("\n[*] Searching for role ID 5179912...");
var rolePatterns = ['"5179912"', ':5179912', '5179912,'];
ranges.forEach(function(range) {
    if (range.size > 50000000 || range.size < 1000) return;

    rolePatterns.forEach(function(pattern) {
        try {
            var results = Memory.scanSync(range.base, range.size, pattern);
            results.slice(0, 5).forEach(function(match) {
                try {
                    var context = Memory.readUtf8String(match.address.sub(30), 200);
                    if (context && context.indexOf('%') === -1) {
                        console.log("\n[ROLE_ID] Found at " + match.address);
                        console.log("[CONTEXT] " + context.replace(/\n/g, ' ').substring(0, 200));
                    }
                } catch(e) {}
            });
        } catch(e) {}
    });
});

console.log("\n[*] Search complete.");
