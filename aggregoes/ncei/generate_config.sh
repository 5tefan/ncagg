#!/usr/bin/env bash
base=${base:-"/nfs/"}

get_sample() {
    echo `ls -d $base/$1/*.nc | tail -1`
}

python aggregoes/init_config_template.py `get_sample spades_mag_prod/inv/GOES-16/MAG-L1b-GEOF/` > aggregoes/ncei/config/mag-l1b-geof.json
python aggregoes/init_config_template.py `get_sample spades_exis_prod/inv/GOES-16/EXIS-L1b-SFXR/` > aggregoes/ncei/config/exis-l1b-sfxr.json
python aggregoes/init_config_template.py `get_sample spades_exis_prod/inv/GOES-16/EXIS-L1b-SFEU/` > aggregoes/ncei/config/exis-l1b-sfeu.json
python aggregoes/init_config_template.py `get_sample spades_seis_prod/inv/GOES-16/SEIS-L1b-EHIS/` > aggregoes/ncei/config/seis-l1b-ehis.json
python aggregoes/init_config_template.py `get_sample spades_seis_prod/inv/GOES-16/SEIS-L1b-MPSH/` > aggregoes/ncei/config/seis-l1b-mpsh.json
python aggregoes/init_config_template.py `get_sample spades_seis_prod/inv/GOES-16/SEIS-L1b-MPSL/` > aggregoes/ncei/config/seis-l1b-mpsl.json
python aggregoes/init_config_template.py `get_sample spades_seis_prod/inv/GOES-16/SEIS-L1b-SGPS/` > aggregoes/ncei/config/seis-l1b-sgps.json
