from typing import List, Optional

from sqlalchemy import (BigInteger, DateTime, ForeignKey, Integer,
                        SmallInteger, String, func)
from sqlalchemy.orm import (DeclarativeBase, Mapped, column_property,
                            mapped_column, relationship)

TinyInteger = SmallInteger


class Base(DeclarativeBase):
    pass


class CommonColumns(Base):
    __abstract__ = True
    _created: Mapped[str] = mapped_column(DateTime, default=func.now())
    _updated: Mapped[str] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    _etag: Mapped[str] = mapped_column(String(40))


class People(CommonColumns):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    firstname: Mapped[str] = mapped_column(String(80))
    lastname: Mapped[str] = mapped_column(String(120))
    fullname: Mapped[str] = column_property(firstname + " " + lastname)


class Invoices(CommonColumns):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[int] = mapped_column(Integer)
    people_id: Mapped[int] = mapped_column(Integer, ForeignKey("people.id"))
    people: Mapped["People"] = relationship(People)


class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    fullname: Mapped[Optional[str]]
    addresses: Mapped[List["Address"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"


class Address(Base):
    __tablename__ = "address"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_address: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    user: Mapped["User"] = relationship(back_populates="addresses")

    def __repr__(self) -> str:
        return f"Address(id={self.id!r}, email_address={self.email_address!r})"


class VUserProfile(Base):
    __tablename__ = "v_user_profile"
    profile_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    profile_name: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(TinyInteger, default=0)
    ws_access_permission: Mapped[int] = mapped_column(TinyInteger, default=0)
    storage_management: Mapped[int] = mapped_column(TinyInteger, default=0)
    search_add_new_camera: Mapped[int] = mapped_column(TinyInteger, default=0)
    set_analytics: Mapped[int] = mapped_column(TinyInteger, default=0)
    create_new_schedule: Mapped[int] = mapped_column(TinyInteger, default=0)
    user_management: Mapped[int] = mapped_column(TinyInteger, default=0)
    config_existing_camera: Mapped[int] = mapped_column(TinyInteger, default=0)
    smart_search: Mapped[int] = mapped_column(TinyInteger, default=0)
    ptz_control: Mapped[int] = mapped_column(TinyInteger, default=0)
    acknowledge_event: Mapped[int] = mapped_column(TinyInteger, default=0)
    archive_view: Mapped[int] = mapped_column(TinyInteger, default=0)
    group_control: Mapped[int] = mapped_column(TinyInteger, default=0)
    download_clip: Mapped[int] = mapped_column(TinyInteger, default=0)
    download_report: Mapped[int] = mapped_column(TinyInteger, default=0)
    secondary_id: Mapped[int] = mapped_column(SmallInteger, default=0)
    unmasked_live_play: Mapped[int] = mapped_column(TinyInteger, default=0)
    unmasked_archive_play: Mapped[int] = mapped_column(TinyInteger, default=0)
    unmasked_clip_download: Mapped[int] = mapped_column(TinyInteger, default=0)
    event_management: Mapped[int] = mapped_column(TinyInteger, default=0)
    system_configuration: Mapped[int] = mapped_column(TinyInteger, default=0)
    system_settings: Mapped[int] = mapped_column(TinyInteger, default=0)
    bookmarks: Mapped[int] = mapped_column(TinyInteger, default=0)
    maps: Mapped[int] = mapped_column(TinyInteger, default=0)
    external_systems: Mapped[int] = mapped_column(TinyInteger, default=0)


class VLoginUser(Base):
    __tablename__ = "v_login_user"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("v_user_profile.profile_id")
    )
    name: Mapped[str] = mapped_column(String(64), default="")
    password: Mapped[str] = mapped_column(String(128), default="")
    mail_id: Mapped[str] = mapped_column(String(128), default="")
    mobile: Mapped[str] = mapped_column(String(16), default="")
    sequrity_question_1: Mapped[str] = mapped_column(String(128), default="")
    sequrity_answer_1: Mapped[str] = mapped_column(String(32), default="")
    sequrity_question_2: Mapped[str] = mapped_column(String(128), default="")
    sequrity_answer_2: Mapped[str] = mapped_column(String(32), default="")
    login_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    logout_timestamp: Mapped[int] = mapped_column(BigInteger, default=0)
    machine_user: Mapped[int] = mapped_column(TinyInteger, default=0)
    machine_id: Mapped[str] = mapped_column(String(32), default="")
    is_encrypted: Mapped[int] = mapped_column(TinyInteger, default=1)
    password_history: Mapped[str] = mapped_column(String(1024), default="")
    double_password: Mapped[int] = mapped_column(SmallInteger, default=0)

    user_profile: Mapped["VUserProfile"] = relationship(
        VUserProfile, cascade="delete"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, password={self.password!r})"

class VChannel(Base):
    __tablename__ = "v_channel"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    model` varchar(64) NOT NULL,
    ip` varchar(16) DEFAULT NULL,
    command_port` smallint(5) unsigned zerofill NOT NULL DEFAULT '00080',
    name` varchar(64) NOT NULL,
    is_ptz` tinyint NOT NULL DEFAULT '0',
    snap_url` varchar(256) DEFAULT NULL,
    analytic_url` varchar(256) DEFAULT NULL,
    minor_url` varchar(256) DEFAULT NULL,
    major_url` varchar(256) DEFAULT NULL,
    username` varchar(16) DEFAULT NULL,
    password` varchar(128) NOT NULL,
    is_encrypted` tinyint NOT NULL DEFAULT '1',
    recording_stream` tinyint NOT NULL,
    ch_number` smallint DEFAULT '0',
    ch_type` smallint NOT NULL,
    latitude` double NOT NULL DEFAULT '0',
    longitude` double NOT NULL DEFAULT '0',
    is_deleted` tinyint NOT NULL DEFAULT '0',
    delete_timestamp` bigint NOT NULL DEFAULT '0',
    analytic_url_multicast` varchar(128) DEFAULT NULL,
    minor_url_multicast` varchar(128) DEFAULT NULL,
    major_url_multicast` varchar(128) DEFAULT NULL,
    current_transmission` tinyint NOT NULL DEFAULT '0',
    description` varchar(256) DEFAULT NULL,
    protocol` tinyint NOT NULL DEFAULT '0',
    channel_index` tinyint NOT NULL DEFAULT '0',
    is_secured` tinyint NOT NULL DEFAULT '0',
    grabber_library` tinyint NOT NULL DEFAULT '0',
    grabbing_protocol` tinyint NOT NULL DEFAULT '1',
    audio_grabbing` tinyint NOT NULL DEFAULT '0',
    
    
# CREATE TABLE `v_channel` (
#   `id` smallint NOT NULL,
#   `model` varchar(64) NOT NULL,
#   `ip` varchar(16) DEFAULT NULL,
#   `command_port` smallint(5) unsigned zerofill NOT NULL DEFAULT '00080',
#   `name` varchar(64) NOT NULL,
#   `is_ptz` tinyint NOT NULL DEFAULT '0',
#   `snap_url` varchar(256) DEFAULT NULL,
#   `analytic_url` varchar(256) DEFAULT NULL,
#   `minor_url` varchar(256) DEFAULT NULL,
#   `major_url` varchar(256) DEFAULT NULL,
#   `username` varchar(16) DEFAULT NULL,
#   `password` varchar(128) NOT NULL,
#   `is_encrypted` tinyint NOT NULL DEFAULT '1',
#   `recording_stream` tinyint NOT NULL,
#   `ch_number` smallint DEFAULT '0',
#   `ch_type` smallint NOT NULL,
#   `latitude` double NOT NULL DEFAULT '0',
#   `longitude` double NOT NULL DEFAULT '0',
#   `is_deleted` tinyint NOT NULL DEFAULT '0',
#   `delete_timestamp` bigint NOT NULL DEFAULT '0',
#   `analytic_url_multicast` varchar(128) DEFAULT NULL,
#   `minor_url_multicast` varchar(128) DEFAULT NULL,
#   `major_url_multicast` varchar(128) DEFAULT NULL,
#   `current_transmission` tinyint NOT NULL DEFAULT '0',
#   `description` varchar(256) DEFAULT NULL,
#   `protocol` tinyint NOT NULL DEFAULT '0',
#   `channel_index` tinyint NOT NULL DEFAULT '0',
#   `is_secured` tinyint NOT NULL DEFAULT '0',
#   `grabber_library` tinyint NOT NULL DEFAULT '0',
#   `grabbing_protocol` tinyint NOT NULL DEFAULT '1',
#   `audio_grabbing` tinyint NOT NULL DEFAULT '0',
#   PRIMARY KEY (`id`)
# ) ENGINE=InnoDB DEFAULT CHARSET=latin1

# CREATE TABLE `v_event` (
#   `id` bigint NOT NULL AUTO_INCREMENT,
#   `channel_id` smallint NOT NULL,
#   `event_type` smallint NOT NULL,
#   `event_message` varchar(256) DEFAULT NULL,
#   `action` varchar(256) NOT NULL,
#   `object_id` varchar(64) DEFAULT NULL,
#   `modified_object_id` varchar(64) DEFAULT NULL,
#   `clip_review` tinyint NOT NULL DEFAULT '0',
#   `acknowledge` tinyint NOT NULL,
#   `acknowledge_user` varchar(16) DEFAULT NULL,
#   `priority` tinyint unsigned NOT NULL,
#   `event_starttime` bigint NOT NULL,
#   `dont_delete` tinyint NOT NULL DEFAULT '0',
#   `zone_id` smallint NOT NULL,
#   `event_endtime` bigint NOT NULL,
#   `escalated_status` tinyint unsigned NOT NULL,
#   `object_property_1` tinyint DEFAULT NULL,
#   `object_property_2` tinyint DEFAULT NULL,
#   `object_property_3` tinyint DEFAULT NULL,
#   `object_property_4` tinyint DEFAULT NULL,
#   `backup_state` tinyint NOT NULL DEFAULT '0',
#   `storage_path` varchar(256) DEFAULT NULL,
#   `rec_server_id` varchar(32) DEFAULT NULL,
#   `attribute` varchar(512) DEFAULT NULL,
#   `secondary_id` bigint NOT NULL DEFAULT '0',
#   PRIMARY KEY (`id`),
#   KEY `FK_v_event_1` (`channel_id`,`event_starttime`) USING BTREE,
#   KEY `event_timestamp` (`event_starttime`) USING BTREE,
#   KEY `new_index` (`channel_id`),
#   CONSTRAINT `new_fk_constraint` FOREIGN KEY (`channel_id`) REFERENCES `v_channel` (`id`) ON DELETE CASCADE
# ) ENGINE=InnoDB AUTO_INCREMENT=15199 DEFAULT CHARSET=latin1



# CREATE TABLE `v_event_snap` (
#   `id` bigint unsigned NOT NULL AUTO_INCREMENT,
#   `snap_url` varchar(256) NOT NULL,
#   `event_id` bigint NOT NULL,
#   `dr_file_fatch_status` smallint NOT NULL DEFAULT '0',
#   `secondary_id` bigint NOT NULL DEFAULT '0',
#   PRIMARY KEY (`id`) USING BTREE,
#   KEY `Index_id` (`id`) USING BTREE,
#   KEY `FK_v_event_snap_url` (`event_id`),
#   CONSTRAINT `FK_v_event_snap_url` FOREIGN KEY (`event_id`) REFERENCES `v_event` (`id`) ON DELETE CASCADE
# ) ENGINE=InnoDB AUTO_INCREMENT=14898 DEFAULT CHARSET=latin1

# CREATE TABLE `v_video_clip_0` (
#   `id` bigint unsigned NOT NULL AUTO_INCREMENT,
#   `channel_id` smallint NOT NULL,
#   `media_server_id` varchar(32) NOT NULL,
#   `start_timestamp` bigint NOT NULL,
#   `end_timestamp` bigint NOT NULL,
#   `clip_size` bigint(20) unsigned zerofill NOT NULL,
#   `clip_url` varchar(256) NOT NULL,
#   `parallel_clip_url` varchar(256) DEFAULT NULL,
#   `junk_flag` tinyint(3) unsigned zerofill NOT NULL,
#   `dont_delete` tinyint NOT NULL,
#   `incident_bookmark` tinyint NOT NULL,
#   `dr_file_fatch_status` smallint NOT NULL DEFAULT '0',
#   `secondary_id` bigint NOT NULL DEFAULT '0',
#   `backup_state` tinyint(3) unsigned zerofill NOT NULL,
#   `storage_path` varchar(256) NOT NULL,
#   `stream_and_clip_mode` tinyint NOT NULL,
#   PRIMARY KEY (`id`),
#   KEY `Index_media_server` (`media_server_id`) USING BTREE,
#   KEY `Index_strattime` (`start_timestamp`) USING BTREE,
#   KEY `channel_id` (`channel_id`),
#   CONSTRAINT `v_video_clip_0_ibfk_1` FOREIGN KEY (`channel_id`) REFERENCES `v_channel` (`id`) ON DELETE CASCADE
# ) ENGINE=InnoDB AUTO_INCREMENT=9962 DEFAULT CHARSET=latin1

# CREATE TABLE `v_heatmap` (
#   `EVENT_ID` bigint NOT NULL AUTO_INCREMENT,
#   `CHANNEL_ID` smallint NOT NULL,
#   `START_TIMESTAMP` bigint NOT NULL,
#   `END_TIMESTAMP` bigint NOT NULL,
#   `HEATMAP_DATA` json DEFAULT NULL,
#   `secondary_id` bigint NOT NULL DEFAULT '0',
#   PRIMARY KEY (`EVENT_ID`),
#   KEY `start_timestamp_heatmap_index` (`START_TIMESTAMP`),
#   KEY `end_timestamp_heatmap_index` (`END_TIMESTAMP`)
# ) ENGINE=InnoDB DEFAULT CHARSET=latin1