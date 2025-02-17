odoo.define('voip.DialingPanel', function (require) {
"use strict";

const PhoneCallActivitiesTab = require('voip.PhoneCallActivitiesTab');
const PhoneCallContactsTab = require('voip.PhoneCallContactsTab');
const PhoneCallRecentTab = require('voip.PhoneCallRecentTab');
const UserAgent = require('voip.UserAgent');

const core = require('web.core');
const config = require('web.config');
const Dialog = require('web.Dialog');
const dom = require('web.dom');
const mobile = require('web_mobile.core');
const realSession = require('web.session');
const Widget = require('web.Widget');

const { _t, _lt } = core;
const HEIGHT_OPEN = '480px';
const HEIGHT_FOLDED = '0px';
const YOUR_ARE_ALREADY_IN_A_CALL = _lt("You are already in a call");

const DialingPanel = Widget.extend({
    template: 'voip.DialingPanel',
    events: {
        'click .o_dial_accept_button': '_onClickAcceptButton',
        'click .o_dial_call_button': '_onClickCallButton',
        'click .o_dial_fold': '_onClickFold',
        'click .o_dial_hangup_button': '_onClickHangupButton',
        'click .o_dial_keypad_backspace': '_onClickKeypadBackspace',
        'click .o_dial_postpone_button': '_onClickPostponeButton',
        'click .o_dial_reject_button': '_onClickRejectButton',
        'click .o_dial_tabs .o_dial_tab': '_onClickTab',
        'click .o_dial_keypad_icon': '_onClickDialKeypadIcon',
        'click .o_dial_number': '_onClickDialNumber',
        'click .o_dial_window_close': '_onClickWindowClose',
        'input .o_dial_search_input': '_onInputSearch',
        'keyup .o_dial_keypad_input': '_onKeyupKeypadInput',
    },
    custom_events: {
        'changeStatus': '_onChangeStatus',
        'fold_panel': '_onFoldPanel',
        'incomingCall': '_onIncomingCall',
        'muteCall': '_onMuteCall',
        'resetMissedCalls': '_resetMissedCalls',
        'showHangupButton': '_onShowHangupButton',
        'sip_accepted': '_onSipAccepted',
        'sip_bye': '_onSipBye',
        'sip_cancel_incoming': '_onSipCancelIncoming',
        'sip_cancel_outgoing': '_onSipCancelOutgoing',
        'sip_customer_unavailable': '_onSipCustomerUnavailable',
        'sip_error': '_onSipError',
        'sip_error_resolved': '_onSipErrorResolved',
        'sip_incoming_call': '_onSipIncomingCall',
        'sip_rejected': '_onSipRejected',
        'switch_keypad': '_onSwitchKeypad',
        'unmuteCall': '_onUnmuteCall',
    },
    /**
     * @constructor
     */
    init() {
        this._super(...arguments);

        this.title = _t("VOIP");

        this._hasIncomingCall = false;
        this._isFolded = false;
        this._isFoldedBeforeCall = false;
        this._isInCall = false;
        this._isMobileDevice = config.device.isMobileDevice;
        this._isPostpone = false;
        this._isShow = false;
        this._isWebRTCSupport = window.RTCPeerConnection && window.MediaStream && navigator.mediaDevices;
        this._onInputSearch = _.debounce(this._onInputSearch.bind(this), 500);
        this._onBackButton = this._onBackButton.bind(this);
        this._tabs = {
            contacts: new PhoneCallContactsTab(this),
            nextActivities: new PhoneCallActivitiesTab(this),
            recent: new PhoneCallRecentTab(this),
        };
        this._userAgent = new UserAgent(this);
        this._missedCounter = 0; // amount of missed call
    },
    /**
     * @override
     */
    async start() {
        this._$callButton = this.$('.o_dial_call_button');
        this._$incomingCallButtons = this.$('.o_dial_incoming_buttons');
        this._$keypad = this.$('.o_dial_keypad');
        this._$keypadInput = this.$('.o_dial_keypad_input');
        this._$keypadInputDiv = this.$('.o_dial_keypad_input_div');
        this._$mainButtons = this.$('.o_dial_main_buttons');
        this._$postponeButton = this.$('.o_dial_postpone_button');
        this._$searchBar = this.$('.o_dial_searchbar');
        this._$searchInput = this.$('.o_dial_search_input');
        this._$tabsPanel = this.$('.o_dial_panel');
        this._$tabs = this.$('.o_dial_tabs');

        this._fetchMissedCallFromServer();

        this._activeTab = this._tabs.nextActivities;
        await this._tabs.contacts.appendTo(this.$('.o_dial_contacts'));
        await this._tabs.nextActivities.appendTo(this.$('.o_dial_next_activities'));
        await this._tabs.recent.appendTo(this.$('.o_dial_recent'));

        this.$el.css('bottom', 0);
        this.$el.hide();
        this._$incomingCallButtons.hide();
        this._$keypad.hide();

        core.bus.on('transfer_call', this, this._onTransferCall);
        core.bus.on('voip_onToggleDisplay', this,  function () {
            this._resetMissedCalls();
            this._onToggleDisplay();
        });

        this.call('bus_service', 'onNotification', this, this._onLongpollingNotifications);

        for (const tab of Object.values(this._tabs)) {
            tab.on('callNumber', this, ev => this._makeCall(ev.data.number));
            tab.on('hidePanelHeader', this, () => this._hideHeader());
            tab.on('showPanelHeader', this, () => this._showHeader());
        }
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Function called when a phonenumber is clicked in the activity widget.
     *
     * @param {Object} params
     * @param {string} params.number
     * @param {integer} params.activityId
     * @return {Promise}
     */
    async callFromActivityWidget(params) {
        if (!this._isInCall) {
            this.$(`
                .o_dial_tab.active,
                .tab-pane.active`
            ).removeClass('active');
            this.$(`
                .o_dial_activities_tab .o_dial_tab,
                .tab-pane.o_dial_next_activities`
            ).addClass('active');
            this._activeTab = this._tabs.nextActivities;
            await this._activeTab.callFromActivityWidget(params);
            return this._makeCall(params.number);
        } else {
            this.do_notify(YOUR_ARE_ALREADY_IN_A_CALL);
        }
    },
    /**
     * Function called when widget phone is clicked.
     *
     * @param {Object} params
     * @param {string} params.number
     * @param {string} params.resModel
     * @param {integer} params.resId
     * @return {Promise}
     */
    async callFromPhoneWidget(params) {
        if (!this._isInCall) {
            this.$(`
                .o_dial_tab.active,
                .tab-pane.active`
            ).removeClass('active');
            this.$(`
                .o_dial_recent_tab .o_dial_tab,
                .tab-pane.o_dial_recent`
            ).addClass('active');
            this._activeTab = this._tabs.recent;
            const phoneCall = await this._activeTab.callFromPhoneWidget(params);
            return this._makeCall(params.number, phoneCall);
        } else {
            this.do_notify(YOUR_ARE_ALREADY_IN_A_CALL);
        }
    },
    /**
     * Function called when a phone number is clicked
     *
     * @return {Object}
     */
    getPbxConfiguration() {
        return this._userAgent.getPbxConfiguration();
    },

    async getMobileCallConfig() {
        return this._userAgent.getMobileCallConfig();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Block the VOIP widget
     *
     * @private
     * @param {string} message  The message we want to show when blocking the
     *   voip widget
     */
    _blockOverlay(message) {
        this._$tabsPanel.block({ message });
        this._$mainButtons.block();
    },
    /**
     * @private
     */
    _cancelCall() {
        $('.o_dial_transfer_button').popover('hide');
        this.$el.css('zIndex', '');
        this._isInCall = false;
        this._isPostpone = false;
        this._hidePostponeButton();
        this._showCallButton();
        this._resetMainButton();
    },
    /**
     * @private
     */
    _fold(animate = true) {
        $('.o_dial_transfer_button').popover('hide');
        if (animate) {
            this.$el.animate({
                height: this._isFolded ? HEIGHT_FOLDED : HEIGHT_OPEN,
            });
        } else {
            this.$el.height(this._isFolded ? HEIGHT_FOLDED : HEIGHT_OPEN);
        }
        if (this._isFolded) {
            this.$('.o_dial_fold').css("bottom", "23px");
            this.$('.o_dial_main_buttons').hide();
            this.$('.o_dial_incoming_buttons').hide();
        } else {
            this.$('.o_dial_fold').css("bottom", 0);
            if (this._hasIncomingCall) {
                this._activeTab._phoneCallDetails.receivingCall();
            } else {
                this.$('.o_dial_main_buttons').show();
            }
        }
    },
    /**
     * Hides the search input and the tabs.
     *
     * @private
     */
    _hideHeader() {
        this._$searchBar.hide();
        this._$tabs.parent().hide();
    },
    /**
     * @private
     */
    _hidePostponeButton() {
        this._$postponeButton.css('visibility', 'hidden');
    },
    /**
     * @private
     * @param {string} number
     * @param {voip.PhonenCall} [phoneCall] if the event function already created a
     *   phonecall; this phonecall is passed to the initPhoneCall function in
     *   order to not create a new one.
     * @return {Promise}
     */
    async _makeCall(number, phoneCall) {
        if (!this._isInCall) {
            if (!await this._useVoip()) {
                // restore the default browser behavior
                const $a = $('<a/>', {
                    href: `tel:${number}`,
                    style: "display:none"
                }).appendTo(document.body);
                $a[0].click();
                $a.remove();
                return;
            }
            if (!this._isWebRTCSupport) {
                this.do_notify(_t("Your browser could not support WebRTC. Please check your configuration."));
                return;
            }
            if (!number) {
                this.do_notify(false, _t("The phonecall has no number"));
                return;
            }
            if (!this._isShow || this._isFolded) {
                await this._toggleDisplay();
            }
            await this._activeTab.initPhoneCall(phoneCall);
            this._userAgent.makeCall(number);
            this._isInCall = true;
        } else {
            this.do_notify(YOUR_ARE_ALREADY_IN_A_CALL);
        }
    },
    /**
     * start a call on ENTER keyup
     *
     * @private
     * @param {KeyEvent} ev
     */
    _onKeyupKeypadInput(ev) {
        if (ev.keyCode === $.ui.keyCode.ENTER) {
            this._onClickCallButton();
        }
    },
    /**
     * @private
     */
    async _fetchMissedCallFromServer() {
        const missedCalls = await this._rpc({
            model: 'voip.phonecall',
            method: 'get_missed_call_info'
        });
        this._missedCounter = missedCalls[0];
        this._refreshMissedCalls();
        if (this._missedCounter > 0) {
            await this._showWidgetFolded();
            this.$('.o_dial_tab.active, .tab-pane.active').removeClass('active');
            this.$('.o_dial_recent_tab .o_dial_tab, .tab-pane.o_dial_recent').addClass('active');
            this._activeTab = this._tabs.recent;
            if (config.device.isMobile) {
                return this._switchToTab("recent");
            }
        }
    },
    /**
     * Refresh the header with amount of missed calls
     *
     * @private
     */
    _refreshMissedCalls() {
        if (this._missedCounter === 0) {
            this.title = _t("VOIP");
        } else {
            this.title = this._missedCounter + " " + _t("missed call(s)");
        }
        $('.o_dial_text').text(this.title);
    },
    /**
     * Refreshes the phonecall list of the active tab.
     *
     * @private
     * @return {Promise}
     */
    async _refreshPhoneCallsStatus() {
        if (this._isInCall) {
            return;
        }
        return this._activeTab.refreshPhonecallsStatus();
    },
    /**
     * @private
     */
    _resetMainButton() {
        this._$mainButtons.show();
        this._$incomingCallButtons.hide();
    },
    /**
     * Reset to 0 amount of missed calls
     *
     * @private
     */
    _resetMissedCalls(data={'data': {'forceReset': false}}) {
        if (this._missedCounter > 0 && (data['data']['forceReset'] || (this._isFolded && this._isShow))) {
            this._missedCounter = 0;
            this._rpc({
                model: 'res.users',
                method: 'reset_last_seen_phone_call',
            });
            this._refreshMissedCalls();
        }
    },
    /**
     * @private
     */
    _showCallButton() {
        this._resetMainButton();
        this._$callButton.addClass('o_dial_call_button');
        this._$callButton.removeClass('o_dial_hangup_button');
        this._$callButton[0].setAttribute('aria-label', _t('Call'));
        this._$callButton[0].title = _t('Call');
    },
    /**
     * @private
     */
    _showHangupButton() {
        this._resetMainButton();
        this._$callButton.removeClass('o_dial_call_button');
        this._$callButton.addClass('o_dial_hangup_button');
        this._$callButton[0].setAttribute('aria-label', _t('End Call'));
        this._$callButton[0].title = _t('End Call');
    },
    /**
     * Shows the search input and the tabs.
     *
     * @private
     */
    _showHeader() {
        this._$searchBar.show();
        this._$tabs.parent().show();
    },
    /**
     * @private
     */
    _showPostponeButton() {
        this._$postponeButton.css('visibility', 'visible');
    },
    /**
     * @private
     * @return {Promise}
     */
    async _showWidget() {
        if (!this._isShow) {
            this.$el.show();
            this._isShow = true;
            mobile.backButtonManager.addListener(this, this._onBackButton);
            this._isFolded = false;
            if (this._isWebRTCSupport) {
                this._$searchInput.focus();
            }
        }
        if (this._isFolded) {
            return this._toggleFold({ isFolded: false });
        }
    },
    /**
     * @private
     * @return {Promise}
     */
    async _showWidgetFolded() {
        if (!this._isShow) {
            this.$el.show();
            this._isShow = true;
            if (!config.device.isMobile) {
                this._isFolded = true;
                this._fold(false);
            }
        }
    },
    /**
     * @param {string} tabName
     * @returns {Promise}
     * @private
     */
    _switchToTab(tabName) {
        this._activeTab = this._tabs[tabName];
        this._$searchInput.val("");
        return this._refreshPhoneCallsStatus();
    },
    /**
     * @private
     * @return {Promise}
     */
    async _toggleDisplay() {
        $('.o_dial_transfer_button').popover('hide');
        if (this._isShow) {
            if (!this._isFolded) {
                this.$el.hide();
                this._isShow = false;
                mobile.backButtonManager.removeListener(this, this._onBackButton);
            } else {
                return this._toggleFold({ isFolded: false });
            }
        } else {
            this.$el.show();
            this._isShow = true;
            mobile.backButtonManager.addListener(this, this._onBackButton);
            if (this._isFolded) {
                await this._toggleFold();
            }
            this._isFolded = false;
            if (this._isWebRTCSupport) {
                this._$searchInput.focus();
            }
        }
    },
    /**
     * @private
     * @param {Object} [param0={}]
     * @param {boolean} [param0.isFolded]
     * @return {Promise}
     */
    async _toggleFold({ isFolded }={}) {
        if (!config.device.isMobile) {
            if (this._isFolded && !this._hasIncomingCall) {
                await this._refreshPhoneCallsStatus();
            }
            this._isFolded = _.isBoolean(isFolded) ? isFolded : !this._isFolded;
            this._fold();
        }
        mobile.backButtonManager[this._isFolded ? 'removeListener' : 'addListener'](this, this._onBackButton);
    },
    /**
     * @private
     */
    _toggleKeypadInputDiv() {
        this._$keypadInputDiv.show();
        if (this._isWebRTCSupport) {
            this._$keypadInput.focus();
        }
    },
    /**
     * Unblock the VOIP widget
     *
     * @private
     */
    _unblockOverlay() {
        this._$tabsPanel.unblock();
        this._$mainButtons.unblock();
    },
    /**
     * Check if the user wants to use voip to make the call.
     * It's check the value res_user field `mobile_call_method` and
     * ask to the end user is choice and update the value as needed
     * @return {Promise<boolean>}
     * @private
     */
    async _useVoip() {
        // Only for mobile device
        if (!config.device.isMobileDevice) {
            return true;
        }

        const mobileCallMethod = await this.getMobileCallConfig();
        // avoid ask choice if value is set
        if (mobileCallMethod !== 'ask') {
            return mobileCallMethod === 'voip';
        }

        const useVOIP = await new Promise(resolve => {
            const $content = $('<main/>', {
                role: 'alert',
                text: _t("Make a call using:")
            });

            const $checkbox = dom.renderCheckbox({
                text: _t("Remember ?"),
            }).addClass('mb-0');

            $content.append($checkbox);

            const processChoice = useVoip => {
                if ($checkbox.find('input[type="checkbox"]').is(':checked')) {
                    this._userAgent.updateCallPreference(realSession.uid, useVoip ? 'voip' : 'phone');
                }
                resolve(useVoip);
            };

            new Dialog(this, {
                size: 'medium',
                fullscreen: false,
                buttons: [{
                    text: _t("Voip"),
                    close: true,
                    click: () => processChoice(true),
                }, {
                    text: _t("Phone"),
                    close: true,
                    click: () => processChoice(false),
                }],
                $content: $content,
                renderHeader: false,
            }).open({shouldFocusButtons: true});
        });
        if (useVOIP && mobile.methods.setupVoip) {
            const hasMicroPhonePermission = await mobile.methods.setupVoip();
            if (!hasMicroPhonePermission) {
                await new Promise(resolve => Dialog.alert(this, _t("You must allow the access to the microphone on your device. Otherwise, the VoIP call receiver will not hear you."), {
                    confirm_callback: resolve,
                }));
            }
        }
        return useVOIP;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    /**
     * Bind directly the DialingPanel#_onClickWindowClose method to the
     * 'backbutton' event.
     *
     * @private
     * @override
     */
    _onBackButton(ev) {
        this._onClickWindowClose(ev);
    },
    /**
     * @private
     */
    _onChangeStatus() {
        this._activeTab.changeRinging();
    },
    /**
     * @private
     */
    _onClickAcceptButton() {
        this._userAgent.acceptIncomingCall();
        this._$mainButtons.show();
        this._$incomingCallButtons.hide();
    },
    /**
     * Method handeling the click on the call button.
     * If a phonecall detail is displayed, then call its first number.
     * If there is a search value, we call it.
     * If we are on the keypad and there is a value, we call it.
     *
     * @private
     * @return {Promise}
     */
    async _onClickCallButton() {
        if (this._isInCall) {
            return;
        }
        if (this.$('.o_phonecall_details').is(':visible')) {
            this._activeTab.callFirstNumber();
            if (this._activeTab.isAutoCallMode) {
                this._showPostponeButton(); //TODO xdo, should be triggered from tab
            }
            return;
        } else if (this._$tabsPanel.is(':visible')) {
            return this._activeTab.callFromTab();
        } else {
            const number = this._$keypadInput.val();
            if (!number) {
                return;
            }
            this._onToggleKeypad();
            this.$(`
                .o_dial_tab.active,
                .tab-pane.active`
            ).removeClass('active');
            this.$(`
                .o_dial_recent_tab .o_dial_tab,
                .tab-pane.o_dial_recent`
            ).addClass('active');
            this._activeTab = this._tabs.recent;
            const phoneCall = await this._activeTab.callFromNumber(number);
            await this._makeCall(number, phoneCall);
            this._$keypadInput.val("");
        }
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickDialKeypadIcon(ev) {
        ev.preventDefault();
        this._onToggleKeypad();
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickDialNumber(ev) {
        ev.preventDefault();
        this._$keypadInput.focus();
        this._onKeypadButtonClick(ev.currentTarget.textContent);
    },
    /**
     * @private
     * @return {Promise}
     */
    async _onClickFold() {
        if (this._isFolded) {
            this._resetMissedCalls();
        }
        return this._toggleFold();
    },
    /**
     * @private
     */
    _onClickHangupButton() {
        this._userAgent.hangup();
        this._cancelCall();
        this._activeTab._selectPhoneCall(this._activeTab._currentPhoneCallId);
    },
    /**
     * @private
     */
    _onClickKeypadBackspace() {
        this._$keypadInput.val(this._$keypadInput.val().slice(0, -1));
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickPostponeButton(ev) {
        if (!this._isInCall) {
            return;
        }
        this._isPostpone = true;
        this._userAgent.hangup();
    },
    /**
     * @private
     */
    _onClickRejectButton() {
        this.$el.css('zIndex', '');
        this._userAgent.rejectIncomingCall();
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    async _onClickTab(ev) {
        ev.preventDefault();
        const tabName = ev.currentTarget.getAttribute('aria-controls');
        return this._switchToTab(tabName);
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickWindowClose(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        $('.o_dial_transfer_button').popover('hide');
        this.$el.hide();
        this._isShow = false;
        mobile.backButtonManager.removeListener(this, this._onBackButton);
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {Object} ev.data contains the number and the partnerId of the caller.
     * @param {string} ev.data.number
     * @param {integer} ev.data.partnerId
     * @return {Promise}
     */
    async _onIncomingCall(ev) {
        this._isFoldedBeforeCall = this._isShow ? this._isFolded : true;
        await this._showWidget();
        this._$keypad.hide();
        this._$tabsPanel.show();
        this.$(`
            .o_dial_tab.active,
            .tab-pane.active`
        ).removeClass('active');
        this.$(`
            .o_dial_recent_tab .o_dial_tab,
            .tab-pane.o_dial_recent`
        ).addClass('active');
        this.$el.css('zIndex', 1051);
        this._activeTab = this._tabs.recent;
        await this._activeTab.onIncomingCall(ev.data);
        this._$mainButtons.hide();
        this._$incomingCallButtons.show();
        this._hasIncomingCall = true;
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @return {Promise}
     */
    _onFoldPanel(ev) {
        return this._toggleFold();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @return {Promise}
     */
    _onInputSearch(ev) {
        return this._activeTab.searchPhoneCall(ev.currentTarget.value.trim());
    },
    /**
     * @private
     * @param {string} number the keypad number clicked
     */
    _onKeypadButtonClick(number) {
        if (this._isInCall) {
            this._userAgent.sendDtmf(number);
        }
        this._$keypadInput.val(this._$keypadInput.val() + number);
    },
    /**
     * @private
     * @param {Object[]} notifications
     * @param {string} [notifications[i].type]
     */
    async _onLongpollingNotifications(notifications) {
        for (const notification of notifications) {
            if (notification[1].type === 'refresh_voip') {
                if (this._isInCall) {
                    return;
                }
                if (this._activeTab === this._tabs.nextActivities) {
                    await this._activeTab.refreshPhonecallsStatus();
                }
            }
        }
    },
    /**
     * @private
     */
    _onMuteCall() {
        this._userAgent.muteCall();
    },
    /**
     * @private
     */
    async _onNotificationRefreshVoip() {
        if (this._isInCall) {
            return;
        }
        if (this._activeTab !== this._tabs.nextActivities) {
            return;
        }
        return this._activeTab.refreshPhonecallsStatus();
    },
    /**
     * @private
     */
    _onShowHangupButton() {
        this._showHangupButton();
    },
    /**
     * @private
     */
    _onSipAccepted() {
        this._activeTab.onCallAccepted();
    },
    /**
     * @private
     */
    async _onSipBye() {
        this._isInCall = false;
        this._showCallButton();
        this._hidePostponeButton();
        const isDone = !this._isPostpone;
        this._isPostpone = false;
        this.$el.css('zIndex', '');
        return this._activeTab.hangupPhonecall(isDone);
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {OdooEvent} ev.data contains the number and the partnerId of the caller
     * @param {string} ev.data.number
     * @param {integer} ev.data.partnerId
     * @return {Promise}
     */
    _onSipCancelIncoming(ev) {
        this._hasIncomingCall = false;
        this._isInCall = false;
        this._isPostpone = false;
        this._missedCounter = this._missedCounter + 1;
        this._refreshMissedCalls();
        this.$el.css('zIndex', '');

        if (this._isFoldedBeforeCall) {
            this._activeTab.onMissedCall(ev.data);
            this.$('.o_dial_tab.active, .tab-pane.active').removeClass('active');
            this.$('.o_dial_recent_tab .o_dial_tab, .tab-pane.o_dial_recent').addClass('active');
            this._activeTab = this._tabs.recent;
            this._isFolded = true;
            this._fold();
        } else {
            this._hidePostponeButton();
            this._showCallButton();
            this._resetMainButton();
            return this._activeTab.onMissedCall(ev.data, true);
        }
    },
    /**
     * @private
     */
    _onSipCancelOutgoing() {
        this._cancelCall();
        this._activeTab.onCancelOutgoingCall();
    },
    /**
     * @private
     */
    _onSipCustomerUnavailable() {
        this.do_notify(false, _t("Customer unavailable. Please try later."));
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {boolean} [ev.data.isConnecting] is true if voip is trying to
     *   connect and the error message must not disappear
     * @param {Object} ev.data.isTemporary it we want to block voip temporarly
     *   to display an error message
     * @param {Object} ev.data.message contains the message to display on the
     *   gray overlay
     */
    _onSipError(ev) {
        const message = ev.data.message;
        this._isInCall = false;
        this._isPostpone = false;
        this._hidePostponeButton();
        if (ev.data.isConnecting) {
            this._blockOverlay(message);
        } else if (ev.data.isTemporary) {
            this._blockOverlay(message);
            this.$('.blockOverlay').on('click', () => this._onSipErrorResolved());
            this.$('.blockOverlay').attr('title', _t("Click to unblock"));
        } else {
            this._blockOverlay(message);
        }
    },
    /**
     * @private
     */
    _onSipErrorResolved() {
        this._unblockOverlay();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {OdooEvent} ev.data contains the number and the partnerId of the caller
     * @param {string} ev.data.number
     * @param {integer} ev.data.partnerId
     * @return {Promise}
     */
    async _onSipIncomingCall(ev) {
        this._onSipErrorResolved();
        if (this._isInCall) {
            return;
        }
        this._isInCall = true;
        this.$(`
            .o_dial_tab.active,
            .tab-pane.active`
        ).removeClass('active');
        this.$(`
            .o_dial_recent_tab .o_dial_tab,
            .tab-pane.o_dial_recent`
        ).addClass('active');
        this.$el.css('zIndex', 1051);
        this._activeTab = this._tabs.recent;
        await this._activeTab.onIncomingCallAccepted(ev.data);
        this._showHangupButton();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {Object} ev.data contains the number and the partnerId of the caller.
     * @param {string} ev.data.number
     * @param {integer} ev.data.partnerId
     * @return {Promise}
     */
    _onSipRejected(ev) {
        this._hasIncomingCall = false;
        this._cancelCall();
        return this._activeTab.onRejectedCall(ev.data);
    },
    /**
     * @private
     */
    _onSwitchKeypad() {
        this._$keypadInput.val(this._$searchInput.val());
        this._onToggleKeypad();
    },
    /**
     * @private
     */
    async _onToggleDisplay() {
        await this._toggleDisplay();
        return this._refreshPhoneCallsStatus();
    },
    /**
     * @private
     */
    _onToggleKeypad() {
        $('.o_dial_transfer_button').popover('hide');
        if (this._$tabsPanel.is(":visible")) {
            this._$tabsPanel.hide();
            this._$keypad.show();
            this._toggleKeypadInputDiv();
        } else {
            this._$tabsPanel.show();
            this._$keypad.hide();
        }
    },
    /**
     * @private
     * @param {string} number
     */
    _onTransferCall(number) {
        this._userAgent.transfer(number);
    },
    /**
     * @private
     */
    _onUnmuteCall() {
        this._userAgent.unmuteCall();
    },
});

return DialingPanel;

});
