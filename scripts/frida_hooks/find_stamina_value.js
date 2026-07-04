/*
 * Frida script to find actual stamina value in game memory
 * Looking for JSON patterns like "stamina":101 or "tili":101
 */

console.log("[*] Searching for stamina value patterns...");

// Search patterns - "tili" is Chinese for stamina, often used in game code
var patterns = [
    '"tili":',      // JSON field
    '"stamina":',   // English JSON field
    'tili=',        // Query string style
    'stamina=',     // Query string style
];

// Get heap ranges
var ranges = Process.enumerateRanges('r--');
console.log("[*] Found " + ranges.length + " readable memory ranges");

var foundCount = 0;
var maxFinds = 20;

// Search through heap-like regions (not code modules)
ranges.forEach(function(range) {
    if (foundCount >= maxFinds) return;

    // Skip very large ranges (likely code) and very small ones
    if (range.size > 50000000 || range.size < 1000) return;

    try {
        patterns.forEach(function(pattern) {
            if (foundCount >= maxFinds) return;

            var results = Memory.scanSync(range.base, range.size, pattern);
            results.forEach(function(match) {
                if (foundCount >= maxFinds) return;

                console.log("\n[FOUND] Pattern '" + pattern + "' at " + match.address);
                try {
                    // Read context around the match
                    var context = Memory.readUtf8String(match.address.sub(20), 150);
                    if (context) {
                        // Filter out chat messages (contain %20 or %22)
                        if (context.indexOf('%20') === -1 && context.indexOf('%22') === -1) {
                            console.log("[CONTEXT] " + context);
                            foundCount++;
                        }
                    }
                } catch(e) {
                    // Try hex dump instead
                    console.log(hexdump(match.address.sub(10), {length: 80, header: false, ansi: false}));
                    foundCount++;
                }
            });
        });
    } catch(e) {
        // Skip inaccessible ranges
    }
});

console.log("\n[*] Found " + foundCount + " potential matches");

// Also try looking for the specific number pattern if we know current stamina
// Current stamina from OCR was 101
console.log("\n[*] Searching for patterns with specific stamina values...");

var staminaValues = [101, 100, 99, 102]; // Common values around current
staminaValues.forEach(function(val) {
    var pattern = '"tili":' + val;
    ranges.forEach(function(range) {
        if (range.size > 50000000 || range.size < 1000) return;
        try {
            var results = Memory.scanSync(range.base, range.size, pattern);
            results.forEach(function(match) {
                console.log("\n[VALUE MATCH] Found " + pattern + " at " + match.address);
                console.log(hexdump(match.address.sub(20), {length: 100, header: false, ansi: false}));
            });
        } catch(e) {}
    });
});

console.log("\n[*] Search complete.");
