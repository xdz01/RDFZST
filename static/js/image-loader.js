// 图片懒加载和优化加载器
class ImageLoader {
    constructor() {
        this.loadedImages = new Set();
        this.observerOptions = {
            root: null,
            rootMargin: '50px 0px',
            threshold: 0.1
        };
        this.init();
    }

    init() {
        // 创建Intersection Observer用于懒加载
        if ('IntersectionObserver' in window) {
        this.imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    if (entry.target.tagName === 'IMG') {
                        this.loadImage(entry.target);
                    } else if (entry.target.dataset.bgImage) {
                        this.loadBackground(entry.target);
                    }
                }
            });
        }, this.observerOptions);
        }

        // 处理页面中所有的懒加载图片
        this.setupLazyLoading();
        
        // 优化正在浏览区域的图片优先加载
        this.prioritizeVisibleImages();
    }

    setupLazyLoading() {
        const lazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]');
        const lazyBackgrounds = document.querySelectorAll('[data-bg-image]');
        
        lazyImages.forEach(img => {
            // 添加加载占位符
            this.addLoadingPlaceholder(img);
            
            // 设置观察器
            if (this.imageObserver) {
                this.imageObserver.observe(img);
            } else {
                // 不支持IntersectionObserver时的回退方案
                this.loadImageFallback(img);
            }
        });
        
        // 处理背景图片懒加载
        lazyBackgrounds.forEach(element => {
            if (this.imageObserver) {
                this.imageObserver.observe(element);
            } else {
                this.loadBackgroundFallback(element);
            }
        });
    }

    loadImage(img) {
        if (this.loadedImages.has(img)) return;
        
        const src = img.dataset.src || img.src;
        if (!src) return;

        // 创建新的Image对象进行预加载
        const tempImg = new Image();
        
        tempImg.onload = () => {
            // 图片加载完成后显示
            if (img.dataset.src) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            }
            
            // 移除加载占位符
            this.removeLoadingPlaceholder(img);
            
            // 添加淡入效果
            img.style.opacity = '0';
            img.style.transition = 'opacity 0.3s ease-in-out';
            setTimeout(() => {
                img.style.opacity = '1';
            }, 10);
            
            // 停止观察该图片
            if (this.imageObserver) {
                this.imageObserver.unobserve(img);
            }
            
            this.loadedImages.add(img);
        };

        tempImg.onerror = () => {
            // 加载失败时的处理
            this.handleImageError(img);
            if (this.imageObserver) {
                this.imageObserver.unobserve(img);
            }
        };

        tempImg.src = src;
    }

    loadImageFallback(img) {
        // 不支持IntersectionObserver时的简单延时加载
        setTimeout(() => {
            this.loadImage(img);
        }, 100);
    }

    loadBackground(element) {
        if (this.loadedImages.has(element)) return;
        
        const bgImage = element.dataset.bgImage;
        if (!bgImage) return;

        // 创建新的Image对象进行预加载
        const tempImg = new Image();
        
        tempImg.onload = () => {
            // 图片加载完成后设置背景
            element.style.backgroundImage = `url('${bgImage}')`;
            
            // 添加淡入效果
            element.style.opacity = '0';
            element.style.transition = 'opacity 0.5s ease-in-out';
            setTimeout(() => {
                element.style.opacity = '1';
            }, 10);
            
            // 移除数据属性
            element.removeAttribute('data-bg-image');
            
            // 停止观察该元素
            if (this.imageObserver) {
                this.imageObserver.unobserve(element);
            }
            
            this.loadedImages.add(element);
        };

        tempImg.onerror = () => {
            // 加载失败时保持占位图
            if (this.imageObserver) {
                this.imageObserver.unobserve(element);
            }
        };

        tempImg.src = bgImage;
    }

    loadBackgroundFallback(element) {
        setTimeout(() => {
            this.loadBackground(element);
        }, 100);
    }

    addLoadingPlaceholder(img) {
        // 添加加载样式
        img.style.background = '#f0f0f0';
        img.style.border = '1px solid #ddd';
        
        // 如果还没有loading属性，添加占位效果
        if (!img.hasAttribute('loading')) {
            img.classList.add('lazy-loading');
        }
    }

    removeLoadingPlaceholder(img) {
        img.style.background = '';
        img.style.border = '';
        img.classList.remove('lazy-loading');
    }

    handleImageError(img) {
        img.src = this.getFallbackImage();
        img.style.opacity = '0.7';
        img.alt = '图片加载失败';
    }

    getFallbackImage() {
        // 返回一个简单的SVG占位图
        return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23f0f0f0'/%3E%3Ctext x='50' y='50' text-anchor='middle' dy='.3em' fill='%23999' font-family='Arial' font-size='12'%3E图片加载失败%3C/text%3E%3C/svg%3E";
    }

    prioritizeVisibleImages() {
        // 优先加载当前视口内的图片
        const visibleImages = this.getVisibleImages();
        visibleImages.forEach(img => {
            if (img.dataset.src && !this.loadedImages.has(img)) {
                // 提高优先级加载
                this.loadImage(img);
            }
        });
    }

    getVisibleImages() {
        const windowHeight = window.innerHeight;
        const visibleImages = [];
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            const rect = img.getBoundingClientRect();
            const isVisible = rect.top < windowHeight && rect.bottom > 0;
            
            if (isVisible) {
                visibleImages.push(img);
            }
        });
        
        return visibleImages;
    }

    // 预加载下一屏的图片
    preloadNextScreen() {
        const nextScreenImages = [];
        const windowHeight = window.innerHeight;
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            const rect = img.getBoundingClientRect();
            const isInNextScreen = rect.top > 0 && rect.top < windowHeight * 2;
            
            if (isInNextScreen) {
                nextScreenImages.push(img);
            }
        });
        
        // 延迟预加载下一屏图片
        setTimeout(() => {
            nextScreenImages.forEach(img => {
                if (img.dataset.src && !this.loadedImages.has(img)) {
                    this.preloadImage(img.dataset.src);
                }
            });
        }, 1000);
    }

    preloadImage(src) {
        const tempImg = new Image();
        tempImg.src = src;
    }
}

// 响应式图片处理
class ResponsiveImageHandler {
    constructor() {
        this.init();
    }

    init() {
        this.setupResponsiveImages();
        window.addEventListener('resize', this.debounce(() => {
            this.setupResponsiveImages();
        }, 250));
    }

    setupResponsiveImages() {
        const responsiveImages = document.querySelectorAll('img[data-srcset]');
        
        responsiveImages.forEach(img => {
            this.updateResponsiveSource(img);
        });
    }

    updateResponsiveSource(img) {
        const srcset = img.dataset.srcset;
        if (!srcset) return;

        const screenWidth = window.innerWidth;
        const sources = this.parseSrcset(srcset);
        const bestSource = this.selectBestSource(sources, screenWidth);
        
        if (bestSource && bestSource !== img.src) {
            img.src = bestSource;
        }
    }

    parseSrcset(srcset) {
        const sources = {};
        srcset.split(',').forEach(item => {
            const [url, width] = item.trim().split(' ');
            if (width) {
                sources[parseInt(width.replace('w', ''))] = url;
            }
        });
        return sources;
    }

    selectBestSource(sources, screenWidth) {
        const widths = Object.keys(sources).map(w => parseInt(w)).sort((a, b) => b - a);
        
        for (const width of widths) {
            if (screenWidth >= width) {
                return sources[width];
            }
        }
        
        return sources[widths[widths.length - 1]] || null;
    }

    debounce(func, wait) {
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
}

// CSS样式注入
const imageLoaderCSS = `
    .lazy-loading {
        filter: blur(3px);
        transition: filter 0.3s ease-in-out;
    }
    
    .lazy-image-loaded {
        filter: none;
    }
    
    .img-container {
        position: relative;
        overflow: hidden;
    }
    
    .img-loading-spinner {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 20px;
        height: 20px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: translate(-50%, -50%) rotate(0deg); }
        100% { transform: translate(-50%, -50%) rotate(360deg); }
    }
    
    img {
        transition: opacity 0.3s ease-in-out;
    }
`;

// 注入CSS样式
function injectImageLoaderStyles() {
    if (!document.getElementById('image-loader-styles')) {
        const style = document.createElement('style');
        style.id = 'image-loader-styles';
        style.textContent = imageLoaderCSS;
        document.head.appendChild(style);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    injectImageLoaderStyles();
    window.imageLoader = new ImageLoader();
    window.responsiveImageHandler = new ResponsiveImageHandler();
    
    // 滚动时预加载下一屏
    let scrollTimer;
    window.addEventListener('scroll', function() {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(function() {
            if (window.imageLoader) {
                window.imageLoader.preloadNextScreen();
            }
        }, 200);
    });
});

// 导出工具函数
window.ImageUtils = {
    // 手动触发懒加载
    triggerLazyLoad: function() {
        if (window.imageLoader) {
            window.imageLoader.prioritizeVisibleImages();
        }
    },
    
    // 预加载指定图片
    preloadImage: function(src) {
        const tempImg = new Image();
        tempImg.src = src;
    },
    
    // 检查图片是否已加载
    isImageLoaded: function(img) {
        return img.complete && img.naturalHeight !== 0;
    }
};