/** @odoo-module */
import { NavBar } from "@web/webclient/navbar/navbar";
import { registry } from "@web/core/registry";
const { fuzzyLookup } = require('@web/core/utils/search');
import { computeAppsAndMenuItems } from "@web/webclient/menus/menu_helpers";
import { onMounted, Component, useRef, useState } from "@odoo/owl";
const commandProviderRegistry = registry.category("command_provider");
import { patch } from "@web/core/utils/patch";
patch(NavBar.prototype, {
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------
    /**
     * @override
     */
     setup() {
        super.setup();
        this.search_input = useRef("search-input")
        this._search_def = new $.Deferred();
        let { apps, menuItems } = computeAppsAndMenuItems(this.menuService.getMenuAsTree("root"));
        this._apps = apps;
        this._searchableMenus = menuItems;
        this.state = useState({
            results : [],
            isSearchOpen: false,
            activeIndex: 0,
        });

        // Intercept Ctrl+K and Escape when App Launcher is visible
        window.addEventListener('keydown', (ev) => {
            const fullscreenMenu = document.querySelector('.dropdown-menu.fullscreen-menu.show');
            if (fullscreenMenu) {
                if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
                    ev.preventDefault();
                    ev.stopPropagation();
                    this.openCustomSearch(ev);
                } else if (ev.key === 'Escape' && this.state.isSearchOpen) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    this.closeCustomSearch(ev);
                }
            }
        }, { capture: true });

        onMounted(() => {
            if (sessionStorage.getItem('app_launcher_open') === 'true') {
                const menuEl = document.querySelector(".dropdown-menu.fullscreen-menu");
                if (menuEl) {
                    menuEl.classList.add("show");
                    const navbar = document.querySelector('.o_main_navbar');
                    if (navbar) navbar.classList.add('app-launcher-open');
                    document.body.classList.add('app-launcher-open');
                }
            }
        });
    },

    _onMenuClick(ev) {
        ev.preventDefault();
        const liEl = ev.currentTarget.closest("li");
        const menuEl = liEl.querySelector(".dropdown-menu");
        menuEl.classList.toggle("show");
        const isShow = menuEl.classList.contains("show");
        sessionStorage.setItem('app_launcher_open', isShow);
        const navbar = document.querySelector('.o_main_navbar');
        if (navbar) navbar.classList.toggle('app-launcher-open', isShow);
        document.body.classList.toggle('app-launcher-open', isShow);
    },

    _closeFullMenu(ev) {
        const dropdownMenu = ev.currentTarget.closest(".dropdown-menu");
        if (dropdownMenu) {
            dropdownMenu.classList.remove("show");
            sessionStorage.setItem('app_launcher_open', 'false');
            const navbar = document.querySelector('.o_main_navbar');
            if (navbar) navbar.classList.remove('app-launcher-open');
            document.body.classList.remove('app-launcher-open');
        }
    },

    openCustomSearch(ev) {
        if (ev) ev.preventDefault();
        this.state.isSearchOpen = true;
        this.state.activeIndex = 0;
        this._searchMenus();
        // Focus and clear the modal search input after it renders
        setTimeout(() => {
            if (this.search_input.el) {
                this.search_input.el.value = "";
                this.search_input.el.focus();
            }
        }, 50);
    },

    closeCustomSearch(ev) {
        this.state.isSearchOpen = false;
        // If a link was clicked, close the main App Launcher as well
        if (ev && ev.currentTarget && ev.currentTarget.tagName === 'A') {
            const dropdownMenu = document.querySelector(".dropdown-menu.fullscreen-menu.show");
            if (dropdownMenu) {
                dropdownMenu.classList.remove("show");
                sessionStorage.setItem('app_launcher_open', 'false');
                const navbar = document.querySelector('.o_main_navbar');
                if (navbar) navbar.classList.remove('app-launcher-open');
            }
        }
    },

    closeCustomSearchIfOutside(ev) {
        if (ev.target.classList.contains('custom-search-overlay')) {
            this.closeCustomSearch();
        }
    },

    onSearchKeyDown(ev) {
        if (!this.state.isSearchOpen || !this.state.results.length) return;

        if (ev.key === 'ArrowDown') {
            ev.preventDefault();
            this.state.activeIndex = Math.min(this.state.activeIndex + 1, this.state.results.length - 1);
            this._scrollToActiveItem();
        } else if (ev.key === 'ArrowUp') {
            ev.preventDefault();
            this.state.activeIndex = Math.max(this.state.activeIndex - 1, 0);
            this._scrollToActiveItem();
        } else if (ev.key === 'Enter') {
            ev.preventDefault();
            const selected = this.state.results[this.state.activeIndex];
            if (selected) {
                this.state.isSearchOpen = false;
                const dropdownMenu = document.querySelector(".dropdown-menu.fullscreen-menu.show");
                if (dropdownMenu) {
                    dropdownMenu.classList.remove("show");
                    sessionStorage.setItem('app_launcher_open', 'false');
                    const navbar = document.querySelector('.o_main_navbar');
                    if (navbar) navbar.classList.remove('app-launcher-open');
                    document.body.classList.remove('app-launcher-open');
                }
                
                const menu = this.menuService.getMenu(selected.id);
                if (menu) {
                    this.menuService.selectMenu(menu);
                }
            }
        }
    },

    _scrollToActiveItem() {
        setTimeout(() => {
            const container = document.querySelector('.custom-search-results');
            const activeEl = document.querySelector('.custom-search-item.active');
            if (container && activeEl) {
                activeEl.scrollIntoView({ block: 'nearest' });
            }
        }, 10);
    },

    _searchMenusSchedule() {
        this._search_def.reject();
        this._search_def = $.Deferred();
        setTimeout(this._search_def.resolve.bind(this._search_def), 50);
        this._search_def.done(this._searchMenus.bind(this));
    },
    
    _searchMenus() {
        var query = this.search_input.el ? this.search_input.el.value : "";
        var results = [];
        
        if (query === "") {
            // Show all apps by default
            this._apps.forEach((menu) => {
                results.push({
                    category: "apps",
                    name: menu.label,
                    actionID: menu.actionID,
                    id: menu.id,
                    webIconData: menu.webIconData ? menu.webIconData.split(',')[1] : null,
                });
            });
            this.state.results = results;
            this.state.activeIndex = 0;
            return;
        }

        fuzzyLookup(query, this._apps, (menu) => menu.label)
        .forEach((menu) => {
            results.push({
                category: "apps",
                name: menu.label,
                actionID: menu.actionID,
                id: menu.id,
                webIconData: menu.webIconData ? menu.webIconData.split(',')[1] : null,
            });
        });
        fuzzyLookup(query, this._searchableMenus, (menu) =>
            (menu.parents + " / " + menu.label).split("/").reverse().join("/"))
        .forEach((menu) => {
            results.push({
                category: "menu_items",
                name: menu.parents + " / " + menu.label,
                actionID: menu.actionID,
                id: menu.id,
            });
        });
        this.state.results = results;
        this.state.activeIndex = 0;
    }
});
