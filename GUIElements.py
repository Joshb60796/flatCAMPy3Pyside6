from PySide6 import QtCore, QtGui, QtWidgets
from copy import copy
#import FlatCAMApp
import re
import logging

log = logging.getLogger('base')


class RadioSet(QtWidgets.QWidget):
    def __init__(self, choices, orientation='horizontal', parent=None):
        """
        The choices are specified as a list of dictionaries containing:

        * 'label': Shown in the UI
        * 'value': The value returned is selected

        :param choices: List of choices. See description.
        :param orientation: 'horizontal' (default) of 'vertical'.
        :param parent: Qt parent widget.
        :type choices: list
        """
        super(RadioSet, self).__init__(parent)
        self.choices = copy(choices)

        if orientation == 'horizontal':
            layout = QtWidgets.QHBoxLayout()
        else:
            layout = QtWidgets.QVBoxLayout()

        group = QtWidgets.QButtonGroup(self)

        for choice in self.choices:
            choice['radio'] = QtWidgets.QRadioButton(choice['label'])
            group.addButton(choice['radio'])
            layout.addWidget(choice['radio'], stretch=0)
            choice['radio'].toggled.connect(self.on_toggle)

        layout.addStretch()
        self.setLayout(layout)

        self.group_toggle_fn = lambda: None

    def on_toggle(self):
        log.debug("Radio toggled")
        radio = self.sender()
        if radio.isChecked():
            self.group_toggle_fn()
        return

    def get_value(self):
        for choice in self.choices:
            if choice['radio'].isChecked():
                return choice['value']
        log.error("No button was toggled in RadioSet.")
        return None

    def set_value(self, val):
        for choice in self.choices:
            if choice['value'] == val:
                choice['radio'].setChecked(True)
                return
        log.error("Value given is not part of this RadioSet: %s" % str(val))


class LengthEntry(QtWidgets.QLineEdit):
    """Length field: stores millimetres, shows ``0.005 in`` / ``1.45 mm``."""

    def __init__(self, output_units='MM', parent=None):
        super(LengthEntry, self).__init__(parent)

        self.display_units = (output_units or "MM").upper()
        if self.display_units not in ("IN", "MM"):
            self.display_units = "MM"
        self.readyToEdit = True

    @property
    def output_units(self):
        return self.display_units

    @output_units.setter
    def output_units(self, val):
        unit = (val or "MM").upper()
        self.display_units = unit if unit in ("IN", "MM") else "MM"

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(LengthEntry, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(LengthEntry, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def returnPressed(self, *args, **kwargs):
        val = self.get_value()
        if val is not None:
            self.set_value(val)
        else:
            log.warning("Could not interpret entry: %s" % self.text())

    def get_value(self):
        """Return millimetres. Updates display_units from a typed suffix."""
        raw = str(self.text()).strip()
        if raw == "":
            return None
        try:
            from units import parse_length
            mm, unit = parse_length(raw, default_unit=self.display_units)
            self.display_units = unit
            return mm
        except Exception:
            log.warning("Could not parse value in entry: %s" % str(raw))
            return None

    def set_value(self, val):
        """
        Show ``val`` with a unit suffix.

        A number is millimetres. A string is parsed (``0.005in``, ``1.45mm``).
        """
        if val is None or val == "":
            self.setText("")
            return
        try:
            from units import format_length, parse_length
        except Exception:
            self.setText(str(val))
            return
        if isinstance(val, str):
            try:
                mm, unit = parse_length(val, default_unit=self.display_units)
                self.display_units = unit
                self.setText(format_length(mm, unit))
                return
            except ValueError:
                self.setText(val)
                return
        try:
            mm = float(val)
        except (TypeError, ValueError):
            self.setText(str(val))
            return
        self.setText(format_length(mm, self.display_units))


class FloatEntry(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super(FloatEntry, self).__init__(parent)
        self.readyToEdit = True

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(FloatEntry, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(FloatEntry, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def returnPressed(self, *args, **kwargs):
        val = self.get_value()
        if val is not None:
            self.set_text(str(val))
        else:
            log.warning("Could not interpret entry: %s" % self.text())

    def get_value(self):
        raw = str(self.text()).strip(' ')
        try:
            evaled = eval(raw)
        except:
            log.error("Could not evaluate: %s" % str(raw))
            return None

        return float(evaled)

    def set_value(self, val):
        self.setText("%.6f" % val)


class IntEntry(QtWidgets.QLineEdit):

    def __init__(self, parent=None, allow_empty=False, empty_val=None):
        super(IntEntry, self).__init__(parent)
        self.allow_empty = allow_empty
        self.empty_val = empty_val
        self.readyToEdit = True

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(IntEntry, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(IntEntry, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def get_value(self):

        if self.allow_empty:
            if str(self.text()) == "":
                return self.empty_val

        return int(self.text())

    def set_value(self, val):

        if val == self.empty_val and self.allow_empty:
            self.setText("")
            return

        self.setText(str(val))


class FCEntry(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super(FCEntry, self).__init__(parent)
        self.readyToEdit = True

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(FCEntry, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(FCEntry, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def get_value(self):
        return str(self.text())

    def set_value(self, val):
        self.setText(str(val))


class EvalEntry(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super(EvalEntry, self).__init__(parent)
        self.readyToEdit = True

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(EvalEntry, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(EvalEntry, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def returnPressed(self, *args, **kwargs):
        val = self.get_value()
        if val is not None:
            self.setText(str(val))
        else:
            log.warning("Could not interpret entry: %s" % self.get_text())

    def get_value(self):
        raw = str(self.text()).strip(' ')
        try:
            return eval(raw)
        except:
            log.error("Could not evaluate: %s" % str(raw))
            return None

    def set_value(self, val):
        self.setText(str(val))


class FCCheckBox(QtWidgets.QCheckBox):
    def __init__(self, label='', parent=None):
        super(FCCheckBox, self).__init__(str(label), parent)

    def get_value(self):
        return self.isChecked()

    def set_value(self, val):
        self.setChecked(val)

    def toggle(self):
        self.set_value(not self.get_value())


class FCTextArea(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super(FCTextArea, self).__init__(parent)

    def set_value(self, val):
        self.setPlainText(val)

    def get_value(self):
        return str(self.toPlainText())

class FCInputDialog(QtWidgets.QInputDialog):
    def __init__(self, parent=None, ok=False, val=None):
        super(FCInputDialog, self).__init__(parent)
        self.allow_empty = ok
        self.empty_val = val
        self.readyToEdit = True

    def mousePressEvent(self, e, Parent=None):
        # required to deselect on 2nd click
        super(FCInputDialog, self).mousePressEvent(e)
        if self.readyToEdit:
            self.selectAll()
            self.readyToEdit = False

    def focusOutEvent(self, e):
        # required to remove cursor on focusOut
        super(FCInputDialog, self).focusOutEvent(e)
        self.deselect()
        self.readyToEdit = True

    def get_value(self, title=None, message=None, min=None, max=None, decimals=None):
        if title is None:
            title = "FlatCAM action"
        if message is None:
            message = "Please enter the value: "
        if min is None:
            min = 0.0
        if max is None:
            max = 100.0
        if decimals is None:
            decimals = 1
        self.val,self.ok = self.getDouble(self, title, message, min=min,
                                                      max=max, decimals=decimals)
        return [self.val,self.ok]

    def set_value(self, val):
        pass


class FCButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super(FCButton, self).__init__(parent)

    def get_value(self):
        return self.isChecked()

    def set_value(self, val):
        self.setText(str(val))


class VerticalScrollArea(QtWidgets.QScrollArea):
    """
    This widget extends QtWidgets.QScrollArea to make a vertical-only
    scroll area that also expands horizontally to accomodate
    its contents.
    """
    def __init__(self, parent=None):
        QtWidgets.QScrollArea.__init__(self, parent=parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def eventFilter(self, source, event):
        """
        The event filter gets automatically installed when setWidget()
        is called.

        :param source:
        :param event:
        :return:
        """
        if event.type() == QtCore.QEvent.Resize and source == self.widget():
            # log.debug("VerticalScrollArea: Widget resized:")
            # log.debug(" minimumSizeHint().width() = %d" % self.widget().minimumSizeHint().width())
            # log.debug(" verticalScrollBar().width() = %d" % self.verticalScrollBar().width())

            self.setMinimumWidth(self.widget().sizeHint().width() +
                                 self.verticalScrollBar().sizeHint().width())

            # if self.verticalScrollBar().isVisible():
            #     log.debug(" Scroll bar visible")
            #     self.setMinimumWidth(self.widget().minimumSizeHint().width() +
            #                          self.verticalScrollBar().width())
            # else:
            #     log.debug(" Scroll bar hidden")
            #     self.setMinimumWidth(self.widget().minimumSizeHint().width())
        return QtWidgets.QWidget.eventFilter(self, source, event)


class OptionalInputSection:

    def __init__(self, cb, optinputs):
        """
        Associates the a checkbox with a set of inputs.

        :param cb: Checkbox that enables the optional inputs.
        :param optinputs: List of widgets that are optional.
        :return:
        """
        assert isinstance(cb, FCCheckBox), \
            "Expected an FCCheckBox, got %s" % type(cb)

        self.cb = cb
        self.optinputs = optinputs

        self.on_cb_change()
        self.cb.stateChanged.connect(self.on_cb_change)

    def on_cb_change(self):

        if self.cb.checkState():

            for widget in self.optinputs:
                widget.setEnabled(True)

        else:

            for widget in self.optinputs:
                widget.setEnabled(False)

