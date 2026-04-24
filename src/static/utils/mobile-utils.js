/**
 * Mobile Utilities for Blixtro IMS
 * Handles Capacitor integration, mobile downloads, and mobile-specific features
 */

(function() {
    'use strict';

    // ==================== CAPACITOR DETECTION ====================
    
    const MobileUtils = {
        isCapacitor: false,
        isMobile: false,
        isIOS: false,
        isAndroid: false,
        capacitor: null,
        browser: null,

        /**
         * Initialize mobile detection
         */
        init() {
            this.detectCapacitor();
            this.detectMobile();
            this.setupMobileViewport();
        },

        /**
         * Detect if running in Capacitor environment
         */
        detectCapacitor() {
            if (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) {
                this.isCapacitor = true;
                this.isIOS = window.Capacitor.getPlatform() === 'ios';
                this.isAndroid = window.Capacitor.getPlatform() === 'android';
                this.capacitor = window.Capacitor;
                this.loadCapacitorPlugins();
                console.log('[MobileUtils] Capacitor detected:', this.isIOS ? 'iOS' : 'Android');
            } else {
                this.isCapacitor = false;
                console.log('[MobileUtils] Running in browser mode');
            }
            window.IS_CAPACITOR = this.isCapacitor;
            window.IS_MOBILE = this.isMobileDevice();
        },

        /**
         * Load Capacitor plugins dynamically
         */
        async loadCapacitorPlugins() {
            if (!this.isCapacitor) return;
            try {
                if (window.Capacitor.Plugins?.Browser) {
                    this.browser = window.Capacitor.Plugins.Browser;
                }
                if (window.Capacitor.Plugins?.Filesystem) {
                    this.filesystem = window.Capacitor.Plugins.Filesystem;
                }
                if (window.Capacitor.Plugins?.FileOpener) {
                    this.fileOpener = window.Capacitor.Plugins.FileOpener;
                }
            } catch (err) {
                console.error('[MobileUtils] Error loading Capacitor plugins:', err);
            }
        },

        /**
         * Detect mobile device
         */
        detectMobile() {
            const userAgent = navigator.userAgent || navigator.vendor || window.opera;
            const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS/i;
            this.isMobile = mobileRegex.test(userAgent) || window.innerWidth <= 768;
            window.addEventListener('resize', () => {
                this.isMobile = mobileRegex.test(userAgent) || window.innerWidth <= 768;
                window.IS_MOBILE = this.isMobile;
            });
        },

        isMobileDevice() {
            return this.isMobile || window.innerWidth <= 768;
        },

        setupMobileViewport() {
            if (this.isCapacitor) {
                document.body.style.overscrollBehavior = 'none';
                this.handleStatusBar();
            }
        },

        async handleStatusBar() {
            if (!this.isCapacitor || !window.Capacitor.Plugins?.StatusBar) return;
            try {
                const { StatusBar } = window.Capacitor.Plugins;
                await StatusBar.setStyle({ style: 'DARK' });
                await StatusBar.setBackgroundColor({ color: '#0d0f14' });
            } catch (err) {
                console.log('[MobileUtils] StatusBar plugin not available');
            }
        }
    };

    // ==================== DOWNLOAD MANAGER ====================
    
    const DownloadManager = {
        async download(url, filename, options = {}) {
            console.log('[DownloadManager] Starting download:', { url, filename, isCapacitor: MobileUtils.isCapacitor });
            
            if (MobileUtils.isCapacitor) {
                return this.downloadNative(url, filename, options);
            } else {
                return this.downloadBrowser(url, filename, options);
            }
        },

        downloadBrowser(url, filename, options) {
            return new Promise((resolve, reject) => {
                try {
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename || 'download';
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    if (options.blob) {
                        link.href = URL.createObjectURL(options.blob);
                    }
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    if (options.blob) {
                        setTimeout(() => URL.revokeObjectURL(link.href), 100);
                    }
                    this.showNotification('Download started', 'success');
                    resolve({ success: true, method: 'browser' });
                } catch (err) {
                    console.error('[DownloadManager] Browser download failed:', err);
                    reject(err);
                }
            });
        },

        async downloadNative(url, filename, options) {
            try {
                if (!window.Capacitor.Plugins?.Filesystem) {
                    return this.downloadBrowser(url, filename, options);
                }

                const { Filesystem, Directory } = window.Capacitor.Plugins;
                
                // Show progress
                this.showNotification('Downloading...', 'info');
                
                const response = await fetch(url, { headers: options.headers || {} });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const blob = await response.blob();
                const arrayBuffer = await blob.arrayBuffer();
                const base64Data = this.arrayBufferToBase64(arrayBuffer);
                
                const mimeType = blob.type || options.mimeType || 'application/octet-stream';
                const finalFilename = filename || `download_${Date.now()}`;
                
                // Write to cache first, then move to downloads
                const result = await Filesystem.writeFile({
                    path: finalFilename,
                    data: base64Data,
                    directory: Directory.Cache,
                    recursive: true
                });
                
                // Move to external storage for user access
                const downloadResult = await Filesystem.writeFile({
                    path: `Download/${finalFilename}`,
                    data: base64Data,
                    directory: Directory.ExternalStorage,
                    recursive: true
                });
                
                this.showNotification(`Saved: ${finalFilename}`, 'success');
                
                if (options.openAfterDownload && window.Capacitor.Plugins?.FileOpener) {
                    await window.Capacitor.Plugins.FileOpener.open({
                        filePath: result.uri,
                        mimeType: mimeType
                    });
                }
                
                return { success: true, method: 'native', uri: result.uri };
            } catch (err) {
                console.error('[DownloadManager] Native download failed:', err);
                this.showNotification('Download failed, trying browser method', 'error');
                return this.downloadBrowser(url, filename, options);
            }
        },

        arrayBufferToBase64(buffer) {
            const bytes = new Uint8Array(buffer);
            let binary = '';
            for (let i = 0; i < bytes.byteLength; i++) {
                binary += String.fromCharCode(bytes[i]);
            }
            return window.btoa(binary);
        },

        showNotification(message, type = 'info') {
            const colors = {
                success: '#10b981',
                error: '#ef4444',
                info: '#6366f1'
            };
            
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                bottom: 100px;
                left: 50%;
                transform: translateX(-50%);
                background: ${colors[type]};
                color: white;
                padding: 12px 24px;
                border-radius: 25px;
                font-weight: 600;
                font-size: 14px;
                z-index: 9999;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                animation: slideUp 0.3s ease;
            `;
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.3s';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    };

    // ==================== MOBILE AUTH ====================
    
    const MobileAuth = {
        async googleLogin(firebaseConfig, options = {}) {
            if (!MobileUtils.isCapacitor) {
                return this.traditionalGoogleLogin(firebaseConfig, options);
            }
            try {
                return await this.capacitorGoogleLogin(firebaseConfig, options);
            } catch (err) {
                console.error('[MobileAuth] Capacitor login failed:', err);
                return this.fallbackEmailLogin(options);
            }
        },

        async traditionalGoogleLogin(firebaseConfig, options) {
            if (!window.firebase) {
                throw new Error('Firebase not loaded');
            }
            const provider = new firebase.auth.GoogleAuthProvider();
            if (options.domain) {
                provider.setCustomParameters({ hd: options.domain });
            }
            const result = await firebase.auth().signInWithPopup(provider);
            const idToken = await result.user.getIdToken();
            return { success: true, idToken, user: result.user, method: 'firebase-popup' };
        },

        async capacitorGoogleLogin(firebaseConfig, options) {
            console.log('[MobileAuth] Using Capacitor Google login flow');
            
            if (!window.firebase?.apps?.length) {
                window.firebase.initializeApp(firebaseConfig);
            }

            const provider = new firebase.auth.GoogleAuthProvider();
            if (options.domain) {
                provider.setCustomParameters({ hd: options.domain });
            }

            sessionStorage.setItem('pendingGoogleLogin', 'true');
            sessionStorage.setItem('loginRedirectUrl', options.redirectUrl || '/');

            await firebase.auth().signInWithRedirect(provider);
            return { success: true, method: 'firebase-redirect' };
        },

        async handleRedirectResult() {
            if (!window.firebase) return null;
            const pendingLogin = sessionStorage.getItem('pendingGoogleLogin');
            if (!pendingLogin) return null;

            try {
                const result = await firebase.auth().getRedirectResult();
                if (result.user) {
                    sessionStorage.removeItem('pendingGoogleLogin');
                    const idToken = await result.user.getIdToken();
                    return { success: true, idToken, user: result.user, method: 'firebase-redirect-result' };
                }
            } catch (err) {
                console.error('[MobileAuth] Redirect result error:', err);
                sessionStorage.removeItem('pendingGoogleLogin');
                throw err;
            }
            return null;
        },

        fallbackEmailLogin(options) {
            return new Promise((resolve, reject) => {
                this.showAlternativeLoginModal(options, resolve, reject);
            });
        },

        showAlternativeLoginModal(options, resolve, reject) {
            const existing = document.getElementById('mobileLoginModal');
            if (existing) existing.remove();

            const modal = document.createElement('div');
            modal.id = 'mobileLoginModal';
            modal.style.cssText = `
                position: fixed;
                inset: 0;
                background: rgba(15, 23, 42, 0.9);
                backdrop-filter: blur(12px);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                animation: fadeIn 0.3s ease;
            `;

            modal.innerHTML = `
                <div style="
                    background: linear-gradient(145deg, #1e293b, #0f172a);
                    border-radius: 24px;
                    padding: 32px 24px;
                    max-width: 360px;
                    width: 100%;
                    text-align: center;
                    border: 1px solid rgba(108, 99, 255, 0.2);
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                ">
                    <div style="
                        width: 72px;
                        height: 72px;
                        background: linear-gradient(135deg, #6366f1, #8b5cf6);
                        border-radius: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 20px;
                        box-shadow: 0 10px 30px rgba(108, 99, 255, 0.3);
                    ">
                        <span class="material-symbols-outlined" style="color: white; font-size: 36px;">login</span>
                    </div>
                    <h3 style="font-weight: 700; margin-bottom: 8px; color: #f1f5f9;">Sign In</h3>
                    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 24px;">
                        Choose your preferred login method
                    </p>
                    
                    <button id="btnGoogleBrowser" style="
                        width: 100%;
                        padding: 14px 20px;
                        background: white;
                        color: #1f2937;
                        border: none;
                        border-radius: 14px;
                        font-weight: 600;
                        font-size: 15px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                        margin-bottom: 12px;
                        transition: all 0.2s;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform=''">
                        <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                        Continue with Google
                    </button>
                    
                    <div style="display: flex; align-items: center; gap: 12px; margin: 16px 0;">
                        <div style="flex: 1; height: 1px; background: rgba(255,255,255,0.1);"></div>
                        <span style="color: #64748b; font-size: 12px;">OR</span>
                        <div style="flex: 1; height: 1px; background: rgba(255,255,255,0.1);"></div>
                    </div>
                    
                    <button id="btnEmailLogin" style="
                        width: 100%;
                        padding: 14px 20px;
                        background: linear-gradient(135deg, #6366f1, #8b5cf6);
                        color: white;
                        border: none;
                        border-radius: 14px;
                        font-weight: 600;
                        font-size: 15px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                        transition: all 0.2s;
                        box-shadow: 0 4px 15px rgba(108, 99, 255, 0.3);
                    " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform=''">
                        <span class="material-symbols-outlined" style="font-size: 20px;">mail</span>
                        Email Login
                    </button>
                    
                    <button id="btnCancelLogin" style="
                        width: 100%;
                        padding: 12px;
                        background: transparent;
                        color: #64748b;
                        border: 1px solid rgba(255,255,255,0.1);
                        border-radius: 14px;
                        font-weight: 500;
                        font-size: 14px;
                        cursor: pointer;
                        margin-top: 12px;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background=''">Cancel</button>
                </div>
            `;

            document.body.appendChild(modal);

            modal.querySelector('#btnGoogleBrowser').addEventListener('click', () => {
                modal.remove();
                if (MobileUtils.browser) {
                    MobileUtils.browser.open({ url: options.authUrl || '/auth/google/' });
                } else {
                    window.location.href = options.authUrl || '/auth/google/';
                }
            });

            modal.querySelector('#btnEmailLogin').addEventListener('click', () => {
                modal.remove();
                this.showEmailLoginForm(options, resolve, reject);
            });

            modal.querySelector('#btnCancelLogin').addEventListener('click', () => {
                modal.remove();
                reject(new Error('Login cancelled'));
            });
        },

        showEmailLoginForm(options, resolve, reject) {
            // Email login form implementation
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                inset: 0;
                background: rgba(15, 23, 42, 0.95);
                z-index: 10001;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            `;
            modal.innerHTML = `
                <div style="
                    background: linear-gradient(145deg, #1e293b, #0f172a);
                    border-radius: 24px;
                    padding: 32px 24px;
                    max-width: 360px;
                    width: 100%;
                    border: 1px solid rgba(108, 99, 255, 0.2);
                ">
                    <h3 style="font-weight: 700; margin-bottom: 8px; color: #f1f5f9; text-align: center;">Email Login</h3>
                    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 24px; text-align: center;">
                        Enter your college email address
                    </p>
                    <form id="emailLoginForm">
                        <div style="margin-bottom: 16px;">
                            <input type="email" id="loginEmail" required placeholder="name@sfscollege.in"
                                style="
                                    width: 100%;
                                    padding: 14px 16px;
                                    background: rgba(15, 23, 42, 0.5);
                                    border: 2px solid rgba(108, 99, 255, 0.2);
                                    border-radius: 14px;
                                    font-size: 15px;
                                    color: #f1f5f9;
                                    outline: none;
                                    transition: all 0.2s;
                                "
                                onfocus="this.style.borderColor='#6366f1'; this.style.boxShadow='0 0 0 3px rgba(108, 99, 255, 0.1)'"
                                onblur="this.style.borderColor='rgba(108, 99, 255, 0.2)'; this.style.boxShadow='none'"
                            >
                        </div>
                        <button type="submit" style="
                            width: 100%;
                            padding: 14px 20px;
                            background: linear-gradient(135deg, #6366f1, #8b5cf6);
                            color: white;
                            border: none;
                            border-radius: 14px;
                            font-weight: 600;
                            font-size: 15px;
                            cursor: pointer;
                            transition: all 0.2s;
                        ">Send Login Link</button>
                    </form>
                    <button id="btnBack" style="
                        width: 100%;
                        padding: 12px;
                        background: transparent;
                        color: #64748b;
                        border: none;
                        font-weight: 500;
                        font-size: 14px;
                        cursor: pointer;
                        margin-top: 16px;
                    ">← Back</button>
                </div>
            `;
            document.body.appendChild(modal);

            modal.querySelector('#emailLoginForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const email = modal.querySelector('#loginEmail').value.trim();

                // Validate email domain
                if (!email.endsWith('@sfscollege.in')) {
                    alert('Please use your official @sfscollege.in email address');
                    return;
                }

                try {
                    const response = await fetch('/api/auth/email-login/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email })
                    });
                    if (response.ok) {
                        modal.innerHTML = `
                            <div style="text-align: center; padding: 40px 20px;">
                                <div style="
                                    width: 80px;
                                    height: 80px;
                                    background: linear-gradient(135deg, #10b981, #059669);
                                    border-radius: 50%;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    margin: 0 auto 20px;
                                    animation: pulse 0.5s ease;
                                ">
                                    <span class="material-symbols-outlined" style="color: white; font-size: 40px;">check</span>
                                </div>
                                <h3 style="font-weight: 700; margin-bottom: 8px; color: #f1f5f9;">Check your email!</h3>
                                <p style="color: #94a3b8; font-size: 14px;">Login link sent to ${email}</p>
                            </div>
                        `;
                        setTimeout(() => {
                            modal.remove();
                            resolve({ success: true, method: 'email-link', email });
                        }, 3000);
                    } else {
                        throw new Error('Failed to send login link');
                    }
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            });

            modal.querySelector('#btnBack').addEventListener('click', () => {
                modal.remove();
                this.showAlternativeLoginModal(options, resolve, reject);
            });
        }
    };

    // ==================== MOBILE FOOTER NAV ====================
    
    const MobileNav = {
        init() {
            console.log('[MobileNav] Initializing...');
            // Always create footer nav, visibility controlled by CSS media query
            this.createFooterNav();
            this.setupSwipeGestures();
            this.setupSidebarVisibility();
            console.log('[MobileNav] Initialization complete');
        },

        setupSidebarVisibility() {
            // Hide sidebar on mobile, show on desktop
            const mediaQuery = window.matchMedia('(max-width: 900px)');
            const handleSidebar = (e) => {
                const sidebar = document.getElementById('mainSidebar');
                const mainContent = document.querySelector('.main-content');
                if (sidebar) {
                    if (e.matches) {
                        // Mobile: hide sidebar by default
                        sidebar.classList.remove('open');
                        if (mainContent) mainContent.style.marginLeft = '0';
                    } else {
                        // Desktop: show sidebar
                        sidebar.style.transform = '';
                        if (mainContent) mainContent.style.marginLeft = '';
                    }
                }
            };
            handleSidebar(mediaQuery);
            mediaQuery.addEventListener('change', handleSidebar);
        },

        createFooterNav(retryCount = 0) {
            console.log('[MobileNav] Creating footer nav... (retry:', retryCount, ')');
            if (document.getElementById('mobileFooterNav')) {
                console.log('[MobileNav] Footer already exists');
                return;
            }

            const navItems = this.getNavItems();
            console.log('[MobileNav] Nav items found:', navItems.length, navItems);
            
            // If no nav items and sidebar doesn't exist yet, retry after delay
            if (!navItems.length && retryCount < 5) {
                const sidebar = document.getElementById('mainSidebar');
                if (!sidebar && retryCount < 5) {
                    console.log('[MobileNav] Sidebar not found, retrying in 300ms...');
                    setTimeout(() => this.createFooterNav(retryCount + 1), 300);
                    return;
                }
                // Try fallback URLs
                console.log('[MobileNav] Using fallback nav items');
                this.createFallbackNavItems();
                return;
            }
            
            if (!navItems.length) {
                console.log('[MobileNav] No nav items after retries, skipping footer creation');
                return;
            }
            this.buildFooter(navItems);
        },

        createFallbackNavItems() {
            // Create minimal fallback items based on URL
            const path = window.location.pathname;
            let items = [{ icon: 'home', label: 'Home', url: '/' }];
            
            if (path.includes('/central-admin/')) {
                items = [
                    { icon: 'dashboard', label: 'Dashboard', url: '/central-admin/dashboard/' },
                    { icon: 'settings', label: 'Settings', url: '/central-admin/aura-dashboard/' }
                ];
            } else if (path.includes('/student/')) {
                items = [
                    { icon: 'edit_note', label: 'Report', url: '/student/report-issue/' },
                    { icon: 'person', label: 'Profile', url: '/student/profile/' }
                ];
            }
            
            this.buildFooter(items);
        },

        buildFooter(navItems) {
            if (document.getElementById('mobileFooterNav')) return;

            const ACC  = '#6c63ff';
            const ACC2 = '#a89dff';
            const GLOW = 'rgba(108,99,255,0.32)';
            const DIM  = '#8a8aaa';

            // ── inject all styles once ──────────────────────────────────
            const style = document.createElement('style');
            style.id = 'mobileNavStyles';
            style.textContent = `
                @keyframes fnSlideUp {
                    from { transform: translateY(120%); opacity: 0; }
                    to   { transform: translateY(0);    opacity: 1; }
                }

                /* ── footer shell ── */
                #mobileFooterNav {
                    position: fixed;
                    bottom: 14px;
                    left: 14px;
                    right: 14px;
                    z-index: 1050;
                    display: none;                          /* JS turns on */
                    border-radius: 26px;
                    padding: 6px 8px;
                    padding-bottom: calc(6px + env(safe-area-inset-bottom, 0px));
                    background: rgba(255,255,255,0.78);
                    backdrop-filter: blur(28px) saturate(210%);
                    -webkit-backdrop-filter: blur(28px) saturate(210%);
                    border: 1px solid rgba(220,218,255,0.70);
                    box-shadow:
                        0 6px 28px rgba(108,99,255,0.12),
                        0 2px 8px  rgba(0,0,0,0.06),
                        inset 0 1px 0 rgba(255,255,255,0.95);
                    animation: fnSlideUp 0.38s cubic-bezier(0.34,1.56,0.64,1) both;
                    /* NO overflow:hidden — scroll must work */
                }

                /* ── scroll strip ── */
                #mobileFooterNav .fn-scroll {
                    overflow-x: auto;
                    overflow-y: visible;          /* don't clip the lifted active item */
                    -webkit-overflow-scrolling: touch;
                    touch-action: pan-x;
                    scrollbar-width: none;
                    -ms-overflow-style: none;
                    /* give a little breathing room so translateY(-4px) isn't clipped */
                    padding: 4px 0 2px;
                    margin: -4px 0 -2px;
                }
                #mobileFooterNav .fn-scroll::-webkit-scrollbar { display: none; }

                /* ── inner flex row ── */
                #mobileFooterNav .fn-row {
                    display: flex;
                    align-items: center;
                    /* min-width:100% fills narrow screen; max-content grows for many items */
                    width: max-content;
                    min-width: 100%;
                    /* distribute items evenly; they will scroll when > viewport */
                    justify-content: space-around;
                    gap: 0;
                    padding: 0 4px;
                    box-sizing: border-box;
                }

                /* ── individual tab ── */
                #mobileFooterNav .fn-item {
                    /* flex: 1 0 AUTO lets items share space but never crush below icon width */
                    flex: 1 0 56px;
                    max-width: 82px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 3px;
                    padding: 4px 2px 4px;
                    text-decoration: none !important;
                    border-radius: 18px;
                    position: relative;
                    transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
                    -webkit-tap-highlight-color: transparent;
                    user-select: none;
                    cursor: pointer;
                }
                #mobileFooterNav .fn-item:active {
                    transform: scale(0.84) !important;
                }

                /* ── icon pill ── */
                #mobileFooterNav .fn-pill {
                    width: 42px;
                    height: 38px;
                    border-radius: 13px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: transparent;
                    transition: background 0.28s cubic-bezier(0.4,0,0.2,1),
                                box-shadow 0.28s ease;
                }
                #mobileFooterNav .fn-pill .material-symbols-outlined {
                    font-size: 21px;
                    color: ${DIM};
                    transition: color 0.25s ease;
                    line-height: 1;
                }

                /* ── label ── */
                #mobileFooterNav .fn-label {
                    font-size: 10px;
                    font-weight: 500;
                    font-family: 'DM Sans', sans-serif;
                    color: ${DIM};
                    white-space: nowrap;
                    transition: color 0.25s ease, font-weight 0.25s ease;
                    line-height: 1;
                }

                /* ── ACTIVE state — driven by class, NOT inline style ── */
                #mobileFooterNav .fn-item.fn-active {
                    transform: translateY(-4px);
                }
                #mobileFooterNav .fn-item.fn-active .fn-pill {
                    background: linear-gradient(135deg, ${ACC}, ${ACC2});
                    box-shadow: 0 4px 14px ${GLOW};
                }
                #mobileFooterNav .fn-item.fn-active .fn-pill .material-symbols-outlined {
                    color: #fff;
                }
                #mobileFooterNav .fn-item.fn-active .fn-label {
                    color: ${ACC};
                    font-weight: 700;
                }
            `;
            if (!document.getElementById('mobileNavStyles')) {
                document.head.appendChild(style);
            }

            // ── build DOM ───────────────────────────────────────────────
            const footer = document.createElement('nav');
            footer.id = 'mobileFooterNav';

            const scrollDiv = document.createElement('div');
            scrollDiv.className = 'fn-scroll';

            const row = document.createElement('div');
            row.className = 'fn-row';

            navItems.forEach((item) => {
                const isActive = item.active !== undefined
                    ? item.active
                    : this.isCurrentPage(item.url);

                const a = document.createElement('a');
                a.href = item.url;
                a.className = 'fn-item' + (isActive ? ' fn-active' : '');

                a.innerHTML = `
                    <div class="fn-pill">
                        <span class="material-symbols-outlined">${item.icon}</span>
                    </div>
                    <span class="fn-label">${item.label}</span>
                `;
                row.appendChild(a);
            });

            scrollDiv.appendChild(row);
            footer.appendChild(scrollDiv);
            document.body.appendChild(footer);

            // Show/hide based on viewport width
            const mq = window.matchMedia('(max-width: 900px)');
            const applyMq = (e) => {
                const mobile = e.matches;
                footer.style.display = mobile ? 'block' : 'none';
                document.body.style.paddingBottom = mobile ? '96px' : '';
                const sidebar = document.getElementById('mainSidebar');
                if (sidebar) sidebar.style.display = mobile ? 'none' : '';
            };
            applyMq(mq);
            mq.addEventListener('change', applyMq);

            console.log('[MobileNav] Light-glass footer created');
        },

        getNavItems() {
            const items = [];
            const path = window.location.pathname;

            // First, try to extract nav items from existing sidebar (server-rendered)
            const sidebar = document.getElementById('mainSidebar');
            if (sidebar) {
                const navLinks = sidebar.querySelectorAll('.navlink');
                navLinks.forEach(link => {
                    const icon = link.querySelector('.material-symbols-outlined');
                    const text = link.querySelector('.menu-text');
                    if (icon && text) {
                        items.push({
                            icon: icon.textContent.trim(),
                            label: text.textContent.trim(),
                            url: link.getAttribute('href'),
                            active: link.classList.contains('active')
                        });
                    }
                });
                if (items.length > 0) return items;
            }

            // Fallback: detect from URL pattern
            const isCentralAdmin = path.includes('/central-admin/');
            const isRoomIncharge = path.includes('/room-incharge/');
            const isStudent = path.includes('/student/');

            if (isCentralAdmin) {
                items.push(
                    { icon: 'dashboard', label: 'Dashboard', url: '/central-admin/dashboard/' },
                    { icon: 'door_open', label: 'Rooms', url: '/central-admin/rooms/' },
                    { icon: 'report', label: 'Issues', url: '/central-admin/issues/' },
                    { icon: 'settings', label: 'Aura', url: '/central-admin/aura-dashboard/' }
                );
            } else if (isRoomIncharge) {
                const roomMatch = path.match(/\/room-incharge\/room\/([^/]+)/);
                const roomSlug = roomMatch ? roomMatch[1] : 'default';
                items.push(
                    { icon: 'dashboard', label: 'Dashboard', url: `/room-incharge/room/${roomSlug}/dashboard/` },
                    { icon: 'list_alt', label: 'Items', url: `/room-incharge/room/${roomSlug}/items/` },
                    { icon: 'report', label: 'Issues', url: `/room-incharge/room/${roomSlug}/issues/` },
                    { icon: 'settings', label: 'Settings', url: `/room-incharge/room/${roomSlug}/settings/` }
                );
            } else if (isStudent) {
                items.push(
                    { icon: 'edit_note', label: 'Report', url: '/student/report-issue/' },
                    { icon: 'history', label: 'History', url: '/student/my-issues/' },
                    { icon: 'person', label: 'Profile', url: '/student/profile/' }
                );
            }

            // Always return at least home link so footer shows
            if (items.length === 0) {
                items.push({ icon: 'home', label: 'Home', url: '/' });
            }

            return items;
        },

        isCurrentPage(url) {
            return window.location.pathname.startsWith(url.replace(/\/$/, ''));
        },

        setupSwipeGestures() {
            let startX = 0;
            document.addEventListener('touchstart', (e) => {
                startX = e.touches[0].clientX;
            }, { passive: true });

            document.addEventListener('touchend', (e) => {
                const endX = e.changedTouches[0].clientX;
                const diffX = endX - startX;
                const sidebar = document.getElementById('mainSidebar');
                
                if (Math.abs(diffX) > 50) {
                    if (diffX > 0 && startX < 50 && window.innerWidth <= 900) {
                        sidebar?.classList.add('open');
                        document.getElementById('sidebarOverlay')?.classList.add('open');
                    } else if (diffX < 0) {
                        sidebar?.classList.remove('open');
                        document.getElementById('sidebarOverlay')?.classList.remove('open');
                    }
                }
            }, { passive: true });
        }
    };

    // ==================== RESPONSIVE CARD FIXES ====================
    
    const ResponsiveCards = {
        init() {
            this.addResponsiveStyles();
        },

        addResponsiveStyles() {
            const style = document.createElement('style');
            style.textContent = `
                /* Email and text overflow fixes */
                .email-cell, .email-text, td[data-label="Email"], 
                .bfc-meta, .room-card-detail-row span:last-child,
                .person-name, .room-card-name, .manager-card h5 {
                    max-width: 100%;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                
                @media (max-width: 768px) {
                    .email-cell, .email-text, td[data-label="Email"],
                    .bfc-meta {
                        white-space: normal;
                        word-break: break-word;
                        overflow-wrap: anywhere;
                        font-size: 13px;
                    }
                    
                    .data-card, .booking-file-card, .room-card {
                        max-width: 100%;
                        overflow: hidden;
                    }
                    
                    .manager-card { padding: 18px !important; }
                    .manager-card h5 {
                        font-size: 14px !important;
                        max-width: 100%;
                    }
                    
                    .booking-file-card { padding: 14px !important; }
                    .bfc-room {
                        max-width: calc(100% - 50px);
                        overflow: hidden;
                        text-overflow: ellipsis;
                    }
                    
                    .action-buttons, .bfc-actions { flex-wrap: wrap; gap: 6px; }
                    
                    .btn-action, .btn-view-file, .btn-dl-file {
                        font-size: 11px !important;
                        padding: 5px 10px !important;
                        white-space: nowrap;
                    }
                    
                    .room-card-detail-row {
                        gap: 8px;
                        flex-wrap: wrap;
                    }
                    
                    .modal-body { max-height: calc(100vh - 120px); }
                    
                    /* Table responsiveness */
                    .table-responsive { max-width: 100%; overflow-x: auto; }
                }
                
                @media (max-width: 380px) {
                    .email-cell, .email-text { font-size: 12px; }
                    .manager-card h5 { font-size: 13px !important; }
                    .room-card-name { font-size: 14px !important; }
                    .badge { font-size: 10px !important; }
                }
            `;
            document.head.appendChild(style);
        }
    };

    // ==================== INITIALIZE ====================
    
    function init() {
        MobileUtils.init();
        ResponsiveCards.init();
        MobileNav.init();
        
        // Handle Firebase redirect result
        MobileAuth.handleRedirectResult().then(result => {
            if (result) {
                console.log('[MobileAuth] Redirect login successful');
                // Submit token to backend
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/auth/firebase-login/';
                const tokenInput = document.createElement('input');
                tokenInput.type = 'hidden';
                tokenInput.name = 'id_token';
                tokenInput.value = result.idToken;
                form.appendChild(tokenInput);
                document.body.appendChild(form);
                form.submit();
            }
        }).catch(err => {
            console.error('[MobileAuth] Redirect result error:', err);
        });
    }

    // Manual force function for testing
    window.forceMobileView = function() {
        console.log('[forceMobileView] Forcing mobile view...');
        const footer = document.getElementById('mobileFooterNav');
        const sidebar = document.getElementById('mainSidebar');
        if (footer) {
            footer.style.display = 'block';
            document.body.style.paddingBottom = '90px';
            console.log('[forceMobileView] Footer shown');
        } else {
            console.log('[forceMobileView] Footer not found, calling MobileNav.init()');
            MobileNav.init();
            setTimeout(() => {
                const f = document.getElementById('mobileFooterNav');
                if (f) {
                    f.style.display = 'block';
                    document.body.style.paddingBottom = '90px';
                }
            }, 100);
        }
        if (sidebar) {
            sidebar.style.display = 'none';
            console.log('[forceMobileView] Sidebar hidden');
        }
    };

    // Expose to global scope
    window.MobileUtils = MobileUtils;
    window.DownloadManager = DownloadManager;
    window.MobileAuth = MobileAuth;
    window.MobileNav = MobileNav;
    window.initMobileFeatures = init;

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Also run after a short delay to ensure DOM is fully ready
    setTimeout(() => {
        if (!document.getElementById('mobileFooterNav')) {
            console.log('[MobileNav] Delayed init - footer not found, reinitializing...');
            MobileNav.init();
        }
    }, 500);

})();

// Add animation keyframes
const animStyle = document.createElement('style');
animStyle.textContent = `
    @keyframes slideUp {
        from { transform: translate(-50%, 20px); opacity: 0; }
        to { transform: translate(-50%, 0); opacity: 1; }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.1); }
    }
`;
document.head.appendChild(animStyle);

// Global forceMobileView - defined outside IIFE for immediate availability
window.forceMobileView = window.forceMobileView || function() {
    console.log('[forceMobileView v2] Forcing mobile view...');
    const footer = document.getElementById('mobileFooterNav');
    const sidebar = document.getElementById('mainSidebar');
    if (footer) {
        footer.style.display = 'block';
        document.body.style.paddingBottom = '90px';
        console.log('[forceMobileView] Footer shown');
    } else {
        console.log('[forceMobileView] Footer not found. Make sure mobile-utils.js is loaded.');
        // Try to manually create minimal footer
        const f = document.createElement('nav');
        f.id = 'mobileFooterNav';
        f.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:9999;display:block;background:rgba(255,255,255,0.75);backdrop-filter:blur(24px) saturate(200%);-webkit-backdrop-filter:blur(24px) saturate(200%);padding:10px 16px;border-top:1px solid rgba(235,235,245,0.9);box-shadow:0 -4px 20px rgba(108,99,255,0.08);';
        f.innerHTML = '<div style="display:flex;justify-content:space-around;color:white;font-size:12px;"><span>Mobile Footer</span></div>';
        document.body.appendChild(f);
        document.body.style.paddingBottom = '70px';
        console.log('[forceMobileView] Emergency footer created');
    }
    if (sidebar) {
        sidebar.style.display = 'none';
        console.log('[forceMobileView] Sidebar hidden');
    }
};

console.log('[mobile-utils.js v3] Loaded successfully');