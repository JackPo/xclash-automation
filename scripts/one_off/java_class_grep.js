// List loaded Java classes that look chat/network related.
Java.perform(function () {
  const patterns = [/chat/i, /world/i, /union/i, /ws/i, /websocket/i, /im/i, /message/i, /proto/i];
  const matches = [];
  Java.enumerateLoadedClasses({
    onMatch: function (name) {
      for (let i = 0; i < patterns.length; i++) {
        if (patterns[i].test(name)) {
          matches.push(name);
          break;
        }
      }
    },
    onComplete: function () {
      matches.sort();
      for (let i = 0; i < matches.length; i++) {
        console.log(matches[i]);
      }
      console.log("DONE classes=" + matches.length);
    }
  });
});
