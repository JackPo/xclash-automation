/**
 * Frida SSL Pinning Bypass Script
 * Works for most Android apps including Unity games
 */

Java.perform(function() {
    console.log("[*] SSL Bypass script loaded");

    // Bypass TrustManagerImpl (Android default)
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        TrustManagerImpl.verifyChain.implementation = function(untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            console.log("[+] Bypassing TrustManagerImpl for: " + host);
            return untrustedChain;
        };
        if (TrustManagerImpl.checkTrustedRecursive) {
            TrustManagerImpl.checkTrustedRecursive.implementation = function() {
                console.log("[+] Bypassing TrustManagerImpl.checkTrustedRecursive");
                return arguments[0];
            };
        }
        if (TrustManagerImpl.checkServerTrusted) {
            TrustManagerImpl.checkServerTrusted.implementation = function() {
                console.log("[+] Bypassing TrustManagerImpl.checkServerTrusted");
                return arguments[0];
            };
        }
        console.log("[*] TrustManagerImpl bypass installed");
    } catch (e) {
        console.log("[-] TrustManagerImpl not found: " + e);
    }

    // Bypass ConscryptFileDescriptorSocket.verifyCertificateChain
    try {
        var ConscryptSocket = Java.use('com.android.org.conscrypt.ConscryptFileDescriptorSocket');
        ConscryptSocket.verifyCertificateChain.implementation = function(certChain, authMethod) {
            console.log("[+] Bypassing ConscryptFileDescriptorSocket.verifyCertificateChain");
            // Don't call original - just return without throwing
        };
        console.log("[*] ConscryptFileDescriptorSocket bypass installed");
    } catch (e) {
        console.log("[-] ConscryptFileDescriptorSocket not found: " + e);
    }

    // Bypass ConscryptEngineSocket.verifyCertificateChain (alternative)
    try {
        var ConscryptEngineSocket = Java.use('com.android.org.conscrypt.ConscryptEngineSocket');
        ConscryptEngineSocket.verifyCertificateChain.implementation = function(certChain, authMethod) {
            console.log("[+] Bypassing ConscryptEngineSocket.verifyCertificateChain");
        };
        console.log("[*] ConscryptEngineSocket bypass installed");
    } catch (e) {
        console.log("[-] ConscryptEngineSocket not found: " + e);
    }

    // Bypass X509TrustManager
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var TrustManager = Java.registerClass({
            name: 'com.frida.TrustManager',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function(chain, authType) {},
                checkServerTrusted: function(chain, authType) {},
                getAcceptedIssuers: function() { return []; }
            }
        });
        console.log("[*] Custom TrustManager registered");
    } catch (e) {
        console.log("[-] X509TrustManager bypass failed: " + e);
    }

    // Patch all loaded X509TrustManager implementations
    try {
        Java.enumerateLoadedClasses({
            onMatch: function(name) {
                try {
                    var klass = Java.use(name);
                    if (klass && klass.checkServerTrusted && klass.checkClientTrusted) {
                        klass.checkServerTrusted.implementation = function() {
                            console.log("[+] Bypassing " + name + ".checkServerTrusted");
                        };
                        klass.checkClientTrusted.implementation = function() {
                            console.log("[+] Bypassing " + name + ".checkClientTrusted");
                        };
                    }
                } catch (e) {}
            },
            onComplete: function() {}
        });
        console.log("[*] Enumerated X509TrustManager implementations");
    } catch (e) {
        console.log("[-] TrustManager enumeration failed: " + e);
    }

    // Bypass SSLContext
    try {
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        var TrustManagerArray = [TrustManager.$new()];
        SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;', '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom').implementation = function(km, tm, sr) {
            console.log("[+] Bypassing SSLContext.init");
            this.init(km, TrustManagerArray, sr);
        };
        console.log("[*] SSLContext bypass installed");
    } catch (e) {
        console.log("[-] SSLContext bypass failed: " + e);
    }

    // Force TrustManagerFactory to return our TrustManager
    try {
        var TrustManagerFactory = Java.use('javax.net.ssl.TrustManagerFactory');
        TrustManagerFactory.getTrustManagers.implementation = function() {
            console.log("[+] Bypassing TrustManagerFactory.getTrustManagers");
            return TrustManagerArray;
        };
        console.log("[*] TrustManagerFactory bypass installed");
    } catch (e) {
        console.log("[-] TrustManagerFactory bypass failed: " + e);
    }

    // Bypass OkHttp3 CertificatePinner (if used)
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log("[+] OkHttp3 CertificatePinner bypassed for: " + hostname);
        };
        console.log("[*] OkHttp3 CertificatePinner bypass installed");
    } catch (e) {
        console.log("[-] OkHttp3 not found: " + e);
    }

    // Bypass OkHttp3 CertificatePinner$Builder
    try {
        var CertificatePinnerBuilder = Java.use('okhttp3.CertificatePinner$Builder');
        CertificatePinnerBuilder.add.overload('java.lang.String', '[Ljava.lang.String;').implementation = function(hostname, pins) {
            console.log("[+] OkHttp3 CertificatePinner.Builder bypassed for: " + hostname);
            return this;
        };
        console.log("[*] OkHttp3 CertificatePinner.Builder bypass installed");
    } catch (e) {
        console.log("[-] OkHttp3 Builder not found: " + e);
    }

    // Bypass Q1 SDK bundled OkHttp3 (com.q1.common.lib.okhttp3)
    try {
        var Q1CertificatePinner = Java.use('com.q1.common.lib.okhttp3.CertificatePinner');
        Q1CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log("[+] Q1 OkHttp3 CertificatePinner bypassed for: " + hostname);
        };
        console.log("[*] Q1 OkHttp3 CertificatePinner bypass installed");
    } catch (e) {
        console.log("[-] Q1 OkHttp3 CertificatePinner not found: " + e);
    }

    // Bypass OkHostnameVerifier (okhttp)
    try {
        var OkHostnameVerifier = Java.use('okhttp3.internal.tls.OkHostnameVerifier');
        OkHostnameVerifier.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function(host, session) {
            console.log("[+] OkHostnameVerifier bypassed for: " + host);
            return true;
        };
        console.log("[*] OkHostnameVerifier bypass installed");
    } catch (e) {
        console.log("[-] OkHostnameVerifier not found: " + e);
    }

    // Bypass Q1 OkHostnameVerifier
    try {
        var Q1OkHostnameVerifier = Java.use('com.q1.common.lib.okhttp3.internal.tls.OkHostnameVerifier');
        Q1OkHostnameVerifier.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function(host, session) {
            console.log("[+] Q1 OkHostnameVerifier bypassed for: " + host);
            return true;
        };
        console.log("[*] Q1 OkHostnameVerifier bypass installed");
    } catch (e) {
        console.log("[-] Q1 OkHostnameVerifier not found: " + e);
    }

    // Bypass CertificateChainCleaner (okhttp)
    try {
        var CertChainCleaner = Java.use('okhttp3.internal.tls.CertificateChainCleaner');
        CertChainCleaner.check.overload('java.lang.String', 'java.util.List').implementation = function(host, chain) {
            console.log("[+] CertificateChainCleaner bypassed for: " + host);
            return chain;
        };
        console.log("[*] CertificateChainCleaner bypass installed");
    } catch (e) {
        console.log("[-] CertificateChainCleaner not found: " + e);
    }

    // Bypass Q1 CertificateChainCleaner
    try {
        var Q1CertChainCleaner = Java.use('com.q1.common.lib.okhttp3.internal.tls.CertificateChainCleaner');
        Q1CertChainCleaner.check.overload('java.lang.String', 'java.util.List').implementation = function(host, chain) {
            console.log("[+] Q1 CertificateChainCleaner bypassed for: " + host);
            return chain;
        };
        console.log("[*] Q1 CertificateChainCleaner bypass installed");
    } catch (e) {
        console.log("[-] Q1 CertificateChainCleaner not found: " + e);
    }

    // Note: Q1 RealConnection hook removed - was breaking connections

    // Bypass Apache HttpClient (older apps)
    try {
        var HttpsURLConnection = Java.use('javax.net.ssl.HttpsURLConnection');
        HttpsURLConnection.setDefaultHostnameVerifier.implementation = function(hostnameVerifier) {
            console.log("[+] Bypassing HttpsURLConnection.setDefaultHostnameVerifier");
        };
        console.log("[*] HttpsURLConnection bypass installed");
    } catch (e) {
        console.log("[-] HttpsURLConnection bypass failed: " + e);
    }

    // Bypass HostnameVerifier
    try {
        var HostnameVerifier = Java.use('javax.net.ssl.HostnameVerifier');
        var TrueVerifier = Java.registerClass({
            name: 'com.frida.TrueVerifier',
            implements: [HostnameVerifier],
            methods: {
                verify: function(hostname, session) {
                    console.log("[+] HostnameVerifier returning true for: " + hostname);
                    return true;
                }
            }
        });
        console.log("[*] HostnameVerifier bypass registered");
    } catch (e) {
        console.log("[-] HostnameVerifier bypass failed: " + e);
    }

    console.log("[*] SSL Bypass script complete - now capturing traffic");
});
