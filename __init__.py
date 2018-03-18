from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import getLogger
from mycroft.util.log import LOG

import sys
import socket
import time
from calendar import timegm
import json
import requests
import re
import urllib

__author__ = 'groupwhere'
_LOGGER = getLogger(__name__)

class TivoDevice(object):
    """Representation of a Tivo receiver on the network."""

    def __init__(self, name, host, port, device, zapuser, zappass, debug=False):
        """Initialize the device."""
        self._name = name
        self._host = host
        self._port = port

        self._zapuser = zapuser
        self._zappass = zappass
        self.usezap = False

        self._channels = {}
        self._titles = {}
        self._is_standby = False
        self._current = {}
        self._ignore = {}
        self.sock = None

        debug = bool(int(debug))
        self.debug = debug

        if zapuser and zappass:
            self.usezap = True
            self.zapget_data()

        self.get_status()

    def connect(self, host, port):
        try:
            if self.debug:
                _LOGGER.warning("Connecting to device...")
            self.sock = socket.socket()
            self.sock.settimeout(5)
            self.sock.connect((host, port))
        except Exception:
            raise

    def disconnect(self):
        if self.debug:
            _LOGGER.warning("Disconnecting from device...")
        self.sock.close()

    def get_status(self):
        if self.debug:
            _LOGGER.warning("get_status called...")
        data = self.send_code('','')
        """ e.g. CH_STATUS 0645 LOCAL """
        """ e.g. CH_STATUS 0645 RECORDING """

        words = data.split()
        self.set_status(words)

    def set_status(self, words):
        if words:
            try:
                if words[0] == "CH_STATUS":
                    #_LOGGER.warning("Got channel status")
                    self._current["channel"] = words[1]
                    self._current["title"]   = "channel " + words[1].strip("0")
                    self._current["status"]  = words[2]
                    self._current["mode"]    = "TV"

#                _LOGGER.warning("USEZAP %s", self.usezap)

                if self.usezap:
                    ch  = str(self._channels.get(words[1]))
                    num = str(words[1]).lstrip("0")
                    ti  = str(self._titles.get(words[1]))
                    if self.debug:
                        _LOGGER.warning("Channel:  %s", num)
                        _LOGGER.warning("Callsign: %s", ch)
                        _LOGGER.warning("Title:    %s", ti)

                    #self._current["title"] = "Ch. " + num + " " + ch + ": " + ti
                    #self._current["title"] = "channel " + ch.strip("0") + " " + ti
                    self._current["title"] = "channel " + num + " " + ti

            except IndexError:
                self._current["channel"] = "no channel"
                self._current["title"]   = "no title"
                self._current["status"]  = "no status"
                self._current["mode"]    = "none"
                if self.debug:
                    _LOGGER.warning("device did not respond correctly...")

    def send_code(self, code, cmdtype="IRCODE", extra=0, bufsize=1024):
        data = ""
        if extra:
            code = code + " " + extra
            # can be '', IRCODE, KEYBOARD, or TELEPORT.  Usually it's IRCODE but we might switch to KEYBOARD since it can do more.

        try:
            self.connect(self._host, self._port)
            if code:
                if cmdtype == '':
                    tosend = code + "\r"
                else:
                    tosend = cmdtype + " " + code + "\r"
            else:
                tosend = ""

            if self.debug:
                _LOGGER.warning("Sending request: '%s'", tosend)

            try:
                self.sock.sendall(tosend.encode())
                time.sleep(0.3)
                data = self.sock.recv(bufsize)
                if self.debug:
                    _LOGGER.warning("Received response: '%s'", data)
            except socket.timeout:
                if self.debug:
                    _LOGGER.warning("Connection timed out...")
                data = b'no_channel Video'

            self.disconnect()
            return data.decode()
        except Exception:
            raise

    def channel_scan(self):
        for i in range(1, self._channel_max):
            res = self.send_code('SETCH', 'IRCODE', str(i))
            words = res.split()
            if words[0] == 'INVALID':
                self._ignore.append(str(i))

    # MediaPlayerDevice properties and methods
    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._is_standby:
            return STATE_OFF
        # Haven't determined a way to see if the content is paused
        return STATE_PLAYING

    def show_live(self):
        data = ""
        """Live TV. """
        """ Any client wishing to set a channel must wait for """
        """ LIVETV_READY before issuing a SETCH or FORCECH command. """
        data = self.send_code('LIVETV', 'TELEPORT')
        self._current["mode"] = "TV"
        return data.decode()

    @property
    def show_guide(self):
        data = ""
        """Guide."""
        """ Also returns status as with NOWPLAYING, e.g. CH_STATUS 0613 LOCAL """
        data = self.send_code('GUIDE', 'TELEPORT')
        self._current["mode"] = "GUIDE"
        return data.decode()

    @property
    def show_tivo(self):
        data = ""
        """Tivo menu."""
        self.send_code('TIVO', 'TELEPORT')
        self._current["mode"] = "MENU"
        return data.decode()

    @property
    def show_now(self):
        data = b""
        """Now playing."""
        data = self.send_code('NOWPLAYING', 'TELEPORT')
        self._current["mode"] = "NOWPLAYING"
        return data.decode()

    def channel_set(self, channel):
        """Channel set."""
        data = self.show_live()
        _LOGGER.debug("LIVE TV STATUS = '%s'", data)
        #if(str(data).strip() == "LIVETV_READY"):
        self.send_code('SETCH', '', channel)

    def media_ch_up(self):
        """Channel up."""
        if self._current["mode"] == "TV":
            data = self.send_code('CHANNELUP')
            words = data.split()
            self._current["channel"] = words[1]
            self._current["title"]   = "Ch. " + words[1]
            self._current["status"]  = words[2]

    def media_ch_dn(self):
        """Channel down."""
        if self._current["mode"] == "TV":
            data = self.send_code('CHANNELDOWN')
            words = data.split()
            self._current["channel"] = words[1]
            self._current["title"]   = "Ch. " + words[1]
            self._current["status"]  = words[2]

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if self._is_standby:
            return None

        return self._current["status"]

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._is_standby:
            return None

        return ""

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_standby:
            return None
        return self._current['title']

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        if self._is_standby:
            return None
        elif 'episodeTitle' in self._current:
            return self._current['episodeTitle']
        return ""

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_TIVO

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._is_standby:
            return

        if 'episodeTitle' in self._current:
            return MEDIA_TYPE_TVSHOW
        return MEDIA_TYPE_VIDEO

    @property
    def media_channel(self):
        """Return the channel current playing media."""
        if self._is_standby:
            return None

        return "{} ({})".format(
            self._current['status'], self._current['channel'])

    @property
    def media_stop(self):
        """Send stop command. """
        if self._is_standby:
            return None

        if self._current["mode"] == "TV":
            return "INTV"

        data = self.send_code('STOP', 'IRCODE', 0, 0)
        words = data.split()
        return words[2]

    @property
    def media_record(self):
        """ Start recording the current program """
        if self._is_standby:
             return

        self.send_code('RECORD', 'IRCODE')

    def turn_on(self):
        """Turn on the receiver. """
        if self._is_standby:
            self.send_code('STANDBY','IRCODE')
            self._is_standby = False

    def turn_off(self):
        """Turn off the receiver. """
        if self._is_standby == False:
            self.send_code('STANDBY','IRCODE')
            self.send_code('STANDBY','IRCODE')
            self._is_standby = True

    def media_play(self):
        """Send play command."""
        if self._is_standby:
            return

        self.send_code('PLAY', 'IRCODE', 0, 0)

    def media_pause(self):
        """Send pause command."""
        if self._is_standby:
            return None

        self.send_code('PAUSE', 'IRCODE', 0, 0)

    def media_previous_track(self):
        """Send rewind command."""
        if self._is_standby:
            return

        if self._current["mode"] in ("TV", "none"):
            self.media_ch_dn()
        else:
            self.send_code('REVERSE', 'IRCODE', 0, 0)

        self.get_status()

    def media_next_track(self):
        """Send fast forward command."""
        if self._is_standby:
            return

        if self._current["mode"] in ("TV", "none"):
            self.media_ch_up()
        else:
            self.send_code('FORWARD', 'IRCODE', 0, 0)

        self.get_status()

    def zap_update(self):
        if self.usezap:
            self.zapget_data()

    def zaplogin(self):
        # Login and fetch a token
        host = 'https://tvlistings.zap2it.com/'
        loginpath = 'api/user/login'
        favpath = 'api/user/favorites'
        login = host + loginpath

        tosend = {'emailid': self._zapuser, 'password': self._zappass, 'usertype': '0', 'facebookuser': 'false'}
        tosend_json = json.dumps(tosend).encode('utf8')
        header = {'content-type': 'application/json'}

        req = requests.post(login, data=tosend_json, headers=header, timeout=5)

        rawrtrn = req.text
        rtrn = json.loads(rawrtrn)

        self._token = rtrn['token']
        if self.debug:
             _LOGGER.warning("Zap token: %s", self._token)
        self._zapprops = rtrn['properties']

        self._zipcode = self._zapprops['2002']
        self._country = self._zapprops['2003']
        (self._lineupId, self._device) = self._zapprops['2004'].split(':')

    def zapget_data(self):
        if self.debug:
            _LOGGER.warning("zapget_data called")
        self.zaplogin()
        now = int(time.time())
        self._channels = {}
        zap_params = self.get_zap_params()
        host = 'https://tvlistings.zap2it.com/'

        # Only get 1 hour of programming since we only need/want the current program titles
        param = '?time=' + str(now) + '&timespan=1&pref=-&' + urllib.urlencode(zap_params) + '&TMSID=&FromPage=TV%20Grid&ActivityID=1&OVDID=&isOverride=true'
        url = host + 'api/grid' + param
        if self.debug:
            _LOGGER.warning("Zapget url: %s", url)

        header = {'X-Requested-With': 'XMLHttpRequest'}

        req = requests.get(url ,headers=header, timeout=5)

        if self.debug:
            self._raw = req.text
            self._zapraw = json.loads(self._raw)

#            f = open('/tmp/zapraw','w')
#            f.write(self._raw)
#            f.close()
        else:
            self._zapraw = json.loads(req.text)

        self.zapget_channels()
        self.zapget_titles()

    def zapget_channels(self):
        # Decode basic channel num to channel name from zap raw data
        if self.debug:
            _LOGGER.warning("zapget_channels called")
        for channelData in self._zapraw['channels']:
            # Pad channel numbers to 4 chars to match values from Tivo device
            _ch = channelData['channelNo'].zfill(4)
            self._channels[_ch] = channelData['callSign']

    def zapget_titles(self):
        # Decode program titles from zap raw data
        if self.debug:
            _LOGGER.warning("zapget_titles called")
        self._titles = {}

        for channelData in self._zapraw['channels']:
            _ch = channelData['channelNo'].zfill(4)
            _ev = channelData['events']

            tmp = _ev[0]
            prog = tmp['program']

            start_utc  = time.strptime(tmp['startTime'], "%Y-%m-%dT%H:%M:%SZ")
            start_time = timegm(start_utc)

            end_utc    = time.strptime(tmp['endTime'], "%Y-%m-%dT%H:%M:%SZ")
            end_time   = timegm(end_utc)

            now = int(time.time())
            if start_time < now < end_time:
                title = prog['title']
                self._titles[_ch] = title

#        if self.debug:
#            _LOGGER.warning("zapget_titles: %s", self._titles)

    def get_zap_params(self):
        zparams = {}

        self._postalcode = self._zipcode
        country = 'USA'
        device = 'X'

        if re.match('[A-z]', self._zipcode):
            country = 'CAN'

            print("testing zlineupid: %s\n" % zlineupId)
            if re.match(':', zlineupId):
                (lineupId, device) = zlineupId.split(':')
            else:
                lineupId = zlineupId
                device   = '-'

            zparams['postalCode'] = self._postalcode
        else:
            zparams['token'] = self._token

        zparams['lineupId']    = self._country + '-' + self._lineupId + '-DEFAULT'
        zparams['headendId']   = self._lineupId
        zparams['device']      = device
        zparams['postalCode']  = self._postalcode
        zparams['country']     = self._country
        zparams['aid']         = 'gapzap'

        return zparams

class TivoSkill(MycroftSkill):
    def __init__(self):
        super(TivoSkill, self).__init__(name="TivoSkill")
        
        self.tivo = None
        self._setup()

    # Create an instance of a Tivo device
    def _setup(self):
        _LOGGER.debug("Attempting to setup TivoSkill")
        if self.config is not None:
            if self.tivo is None:
                self.tivo = TivoDevice(
                    self.config.get('name'),
                    self.config.get('host'),
                    int(self.config.get('port')),
                    0,
                    self.config.get('zapuser'),
                    self.config.get('zappass'),
                    self.config.get('debug')
                    )
        else:
            self.tivo = None

    @intent_handler(IntentBuilder("").require("Tivo").require("Status"))
    def handle_tivo_status_intent(self, message):
        statuswords = None
        self.tivo.get_status()

        if self.tivo._current["mode"] == "TV":
            statuswords = "watching " + self.tivo._current["title"]

        self.speak_dialog("tivo.status", data={"dev_name": self.tivo._name, "status": statuswords})

    @intent_handler(IntentBuilder("").require("Tivo").require("Play"))
    def handle_tivo_play_intent(self, message):
        statuswords = None
        self.tivo.media_play()
        self.speak_dialog("tivo.playpause", data={"dev_name": self.tivo._name, "status": "playing"})

    @intent_handler(IntentBuilder("").require("Tivo").require("Pause"))
    def handle_tivo_pause_intent(self, message):
        statuswords = None
        self.tivo.media_pause()
        self.speak_dialog("tivo.playpause", data={"dev_name": self.tivo._name, "status": "paused"})

    # Record or Stop
    @intent_handler(IntentBuilder("").require("Tivo").require("Record"))
    def handle_tivo_play_intent(self, message):
        if message.data["Record"] == "record":
            self.tivo.media_record()
            self.speak_dialog("tivo.status", data={"dev_name": self.tivo._name, "status": "recording"})
        else: # assume stop
            self.tivo.media_stop()
            self.speak_dialog("tivo.status", data={"dev_name": self.tivo._name + " recording", "status": "stopped"})

    # On or off
    @intent_handler(IntentBuilder("").require("Tivo").require("OnOff"))
    def handle_power_intent(self, message):
        if message.data["OnOff"] == "off":
            self.tivo.turn_off()
        else:  # assume "on"
            self.tivo.turn_on()

        self.speak_dialog("tivo.playpause", data={"dev_name": self.tivo._name, "status": message.data["OnOff"]})

    # Channel up, down, or set to number
    @intent_handler(IntentBuilder("").require("Tivo").require("Channel").require("Dir"))
    def handle_channel_intent(self, message):
        updown = False
        if message.data["Dir"] == "up":
            updown = True
            self.tivo.media_next_track()
        elif message.data["Dir"] == "down":
            updown = True
            self.tivo.media_previous_track()
        else:
            channel = message.utterance_remainder()
            # Join 6 1 2 into 612
            channel = channel.replace(" ", "")
            # Pad to the left with zeroes (612 becomes 0612)
            channel = channel.zfill(4)
            #_LOGGER.debug("CHANNEL SET COMMAND %s", channel)

            self.tivo.channel_set(channel)

        if self.tivo._current["mode"] == "TV":
            statuswords = "watching " + self.tivo._current["title"]

        self.speak_dialog("tivo.status", data={"dev_name": self.tivo._name, "status": statuswords})

def create_skill():
    return TivoSkill()
