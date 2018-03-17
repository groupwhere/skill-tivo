## skill-tivo
Tivo skill for Mycroft

## Description 
Based on ideas from the following sites:
```
https://community.home-assistant.io/t/control-tivo-box-over-telnet/12430/65
https://www.tivocommunity.com/community/index.php?threads/tivo-ui-control-via-telnet-no-hacking-required.392385/
https://community.home-assistant.io/t/tivo-media-player-component/851
https://charliemeyer.net/2012/12/04/remote-control-of-a-tivo-from-the-linux-command-line/
```

Add the following to your mycroft.conf and restart mycroft-skills
```
  "TivoSkill": {
    "name": "Name for your deivce",
    "host": "192.168.0.84",
    "port": 31339,
    "zapuser": "your@email.addr",
    "zappass": "YOURZAP2ITPASS",
    "debug": false
  }
```

Port should always be 31339.  Zap2iT is optional but will allow mycroft to tell you what is playing on the current channel.  Without it, it will only tell you the channel.

## Currently, only the following functions work:
* "Tivo status"
* "Tivo channel up"
* "Tivo channel down"

Mycroft will respond with, e.g., "Bob's Tivo is currently watching channel 231 Raider's of the Lost Ark."
