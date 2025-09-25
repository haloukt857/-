/**
 * OKX风格移动端增强功能
 * 提供移动端适配、触摸交互和响应式优化
 */

(function() {
    'use strict';
    
    // 检测移动设备
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    
    // 移动端类添加
    if (isMobile || isTouch) {
        document.documentElement.classList.add('mobile-device');
    }
    
    // 防抖函数
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // 响应式导航菜单
    function initMobileNav() {
        // 确保导航在移动端可以正常工作
        const navToggle = document.querySelector('.navbar-toggle');
        const navMenu = document.querySelector('.navbar-menu');
        
        if (navToggle && navMenu) {
            navToggle.addEventListener('click', function() {
                navMenu.classList.toggle('show');
            });
        }
        
        // 点击外部关闭菜单 - 修复快速点击导航链接的问题
        const closeMenuHandler = debounce(function(event) {
            // 如果点击的是导航链接，不要阻止跳转
            if (event.target.matches('a[href]') || event.target.closest('a[href]')) {
                return;
            }
            
            if (navMenu && !navToggle.contains(event.target) && !navMenu.contains(event.target)) {
                navMenu.classList.remove('show');
            }
        }, 100);
        
        document.addEventListener('click', closeMenuHandler);
        
        // 修复导航链接快速点击问题
        const navLinks = document.querySelectorAll('nav a[href], .navbar a[href]');
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                // 确保链接点击不被其他事件处理程序阻止
                e.stopPropagation();
            });
        });
    }
    
    // 触摸友好的卡片交互
    function initTouchInteractions() {
        const cards = document.querySelectorAll('.card');
        
        cards.forEach(card => {
            // 添加触摸反馈
            card.addEventListener('touchstart', function() {
                this.classList.add('touch-active');
            });
            
            card.addEventListener('touchend', function() {
                setTimeout(() => {
                    this.classList.remove('touch-active');
                }, 150);
            });
        });
    }
    
    // 移动端表单优化
    function initMobileForm() {
        const inputs = document.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            // 输入聚焦时滚动到视图
            input.addEventListener('focus', function() {
                if (isMobile) {
                    setTimeout(() => {
                        this.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                        });
                    }, 300);
                }
            });
        });
    }
    
    // 虚拟键盘适配
    function handleVirtualKeyboard() {
        if (!isMobile) return;
        
        const viewport = document.querySelector('meta[name="viewport"]');
        
        // 输入框聚焦时调整视图
        document.addEventListener('focusin', function(e) {
            if (e.target.matches('input, textarea')) {
                // 防止缩放
                if (viewport) {
                    viewport.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0');
                }
                
                // 添加键盘激活类
                document.body.classList.add('keyboard-active');
            }
        });
        
        document.addEventListener('focusout', function(e) {
            if (e.target.matches('input, textarea')) {
                // 恢复正常缩放
                if (viewport) {
                    viewport.setAttribute('content', 'width=device-width, initial-scale=1.0, user-scalable=1');
                }
                
                // 移除键盘激活类
                document.body.classList.remove('keyboard-active');
            }
        });
    }
    
    // 滚动优化
    function initScrollOptimization() {
        let ticking = false;
        
        function updateScrollState() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            // 导航栏背景透明度
            const navbar = document.querySelector('.navbar');
            if (navbar) {
                if (scrollTop > 50) {
                    navbar.classList.add('scrolled');
                } else {
                    navbar.classList.remove('scrolled');
                }
            }
            
            ticking = false;
        }
        
        window.addEventListener('scroll', function() {
            if (!ticking) {
                requestAnimationFrame(updateScrollState);
                ticking = true;
            }
        });
    }
    
    // 响应式表格处理
    function initResponsiveTables() {
        const tables = document.querySelectorAll('table');
        
        tables.forEach(table => {
            // 为移动端表格添加滚动容器
            if (!table.parentElement.classList.contains('table-responsive')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-responsive';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
    }
    
    // 性能优化 - 图片懒加载
    function initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            observer.unobserve(img);
                        }
                    }
                });
            });
            
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }
    
    // 通知系统
    function initNotificationSystem() {
        // 简单的toast通知
        window.showToast = function(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <div class="toast-content">
                    <span class="toast-icon">${getToastIcon(type)}</span>
                    <span class="toast-message">${message}</span>
                </div>
            `;
            
            document.body.appendChild(toast);
            
            // 显示动画
            setTimeout(() => toast.classList.add('show'), 100);
            
            // 自动移除
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => document.body.removeChild(toast), 300);
            }, 3000);
        };
        
        function getToastIcon(type) {
            const icons = {
                success: '✅',
                error: '❌',
                warning: '⚠️',
                info: 'ℹ️'
            };
            return icons[type] || icons.info;
        }
    }
    
    // 初始化所有功能
    function init() {
        // DOM 加载完成后执行
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }
        
        initMobileNav();
        initTouchInteractions();
        initMobileForm();
        handleVirtualKeyboard();
        initScrollOptimization();
        initResponsiveTables();
        initLazyLoading();
        initNotificationSystem();
        
        // 添加全局样式类
        document.body.classList.add('okx-enhanced');
    }
    
    // 强制应用OKX风格
    function forceOKXTheme() {
        // 确保DOM元素存在后再操作
        if (!document.body || !document.documentElement) return;
        
        // 强制设置页面背景色
        document.body.style.backgroundColor = '#000000';
        document.documentElement.style.backgroundColor = '#000000';
        
        // 强制所有卡片使用OKX风格
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            card.style.backgroundColor = '#1a1a1a';
            card.style.borderColor = '#333333';
            card.style.color = '#ffffff';
        });
        
        // 强制所有按钮使用OKX风格
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(btn => {
            if (btn.classList.contains('btn-primary')) {
                btn.style.backgroundColor = '#10b981';
                btn.style.color = '#000000';
            } else if (btn.classList.contains('btn-secondary')) {
                btn.style.backgroundColor = '#1a1a1a';
                btn.style.color = '#ffffff';
                btn.style.borderColor = '#333333';
            } else if (btn.classList.contains('btn-error')) {
                btn.style.backgroundColor = '#ef4444';
                btn.style.color = '#ffffff';
            }
        });
        
        // 强制所有输入框使用OKX风格
        const inputs = document.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.style.backgroundColor = '#1a1a1a';
            input.style.borderColor = '#2a2a2a';
            input.style.color = '#ffffff';
        });
        
        // 强制导航栏使用OKX风格
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            navbar.style.backgroundColor = '#0a0a0a';
            navbar.style.borderBottomColor = '#2a2a2a';
        }
    }
    
    // 启动初始化
    init();
    
    // 立即应用OKX主题
    forceOKXTheme();
    
    // 每秒检查一次并重新应用主题（确保动态加载的内容也能应用）
    setInterval(forceOKXTheme, 1000);
    
    // 窗口大小变化时重新初始化响应式组件
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            initResponsiveTables();
        }, 250);
    });
    
})();