"""
Utilities for including widgets in designer with custom edit widgets, etc.
"""
from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any

from pydm.widgets.base import PyDMWidget
from pydm.widgets.qtplugin_extensions import PyDMExtension
from qtpy.QtCore import Property, QObject
from qtpy.QtWidgets import QAction, QDialog, QVBoxLayout


class DeviceSource(Enum):
    AUTO = "auto"
    HAPPI = "happi"
    EXPLICIT = "explicit"


class DeviceMaker:
    def make_device(self) -> Any:
        raise NotImplementedError()

    def for_json(self) -> str:
        return "auto"


@dataclasses.dataclass
class HappiMaker(DeviceMaker):
    name: str

    def for_json(self) -> dict[str, str]:
        return {
            "name": self.name,
        }


@dataclasses.dataclass
class ExplicitMaker(DeviceMaker):
    module: str
    cls: str
    args: list[Any]
    kwargs: dict[str, Any]

    def for_json(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "cls": self.cls,
            "args": self.args,
            "kwargs": self.kwargs,
        }


@dataclasses.dataclass
class DeviceInstructions:
    source: DeviceSource
    subattr: str
    handler: DeviceMaker

    @classmethod
    def from_json(self, blob: str) -> DeviceInstructions:
        data = json.loads(blob)
        source = data["source"]
        if source == DeviceSource.AUTO.value:
            handler = DeviceMaker()
        elif source == DeviceSource.HAPPI.value:
            handler = HappiMaker(
                name=data["handler"]["name"]
            )
        elif source == DeviceSource.EXPLICIT.value:
            handler = ExplicitMaker(
                module=data["handler"]["module"],
                cls=data["handler"]["cls"],
                args=data["handler"]["args"],
                kwargs=data["handler"]["kwargs"],
            )
        else:
            raise NotImplementedError()
        return DeviceInstructions(
            source=source,
            subattr=data["subattr"],
            handler=handler,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.name,
            "subattr": self.subattr,
            "handler": self.handler.for_json(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def make(self) -> Any:
        device = self.handler.make_device()
        subattr = self.subattr
        while subattr:
            device = getattr(device, subattr)
            subattr = ".".join(subattr.split(".")[1:])
        return device


class DeviceSourceEditor(QDialog):
    def __init__(
        self,
        widget: TyphosDeviceMixin,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setLayout(QVBoxLayout())


class AddDeviceExtension(PyDMExtension):
    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self.device_source_action = QAction(
            "Select &device source...",
            self.widget,
        )
        self.device_source_action.triggered.connect(self.open_dialog)

    def open_dialog(self, state):
        dialog = DeviceSourceEditor(self.widget, parent=None)
        dialog.exec_()

    def actions(self):
        return [self.device_source_action]


class TyphosDeviceMixin(PyDMWidget):
    """
    A mixin class used to display Typhos widgets in the Qt designer.
    """
    _qt_designer_ = {
        "group": "Typhos Widgets",
        "is_container": False,
        "extensions": [AddDeviceExtension],
    }

    # Unused properties that we don't want visible in designer
    alarmSensitiveBorder = Property(bool, designable=False)
    alarmSensitiveContent = Property(bool, designable=False)
    precisionFromPV = Property(bool, designable=False)
    precision = Property(int, designable=False)
    showUnits = Property(bool, designable=False)

    @Property(str)
    def device_source(self):
        """Instructions for how to create the device."""
        try:
            return self._device_source_raw
        except AttributeError:
            return ""

    @device_source.setter
    def device_source(self, value):
        self._device_source_raw = value
        try:
            self._device_instr = DeviceInstructions.from_json(value)
        except Exception:
            self._device_instr = None
        else:
            if not self.is_auto():
                self.add_device(self._device_instr.make())

    def is_auto(self) -> bool:
        if self._device_instr is None:
            return True
        else:
            return self._device_instr.source == DeviceSource.AUTO

    # Backcompat with channel, old property
    @Property(str, designable=False)
    def channel(self):
        return None

    @channel.setter
    def channel(self, value):
        raise NotImplementedError()
