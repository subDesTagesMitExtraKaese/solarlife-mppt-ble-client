#include "solarlife_mppt.h"

#ifdef USE_ESP32

#include <cinttypes>
#include <cstring>

#include "esphome/core/log.h"

namespace esphome::solarlife_mppt {

namespace espbt = esphome::esp32_ble_tracker;

static const char *const TAG = "solarlife_mppt";

void SolarlifeMppt::setup() {
  this->parameters_due_ = true;
  this->frame_length_ = 0;
  this->state_ = State::IDLE;
}

void SolarlifeMppt::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Solarlife MPPT:\n"
                "  Service UUID: 0x%04X\n"
                "  Notify UUID: 0x%04X\n"
                "  Write UUID: 0x%04X\n"
                "  Retries: %u\n"
                "  Timeout: %" PRIu32 " ms\n"
                "  Parameters interval: %" PRIu32 " ms",
                this->service_uuid_, this->notify_uuid_, this->write_uuid_, this->retries_, this->timeout_,
                this->parameters_interval_);
  LOG_UPDATE_INTERVAL(this);
}

const Register *SolarlifeMppt::find_register(const char *name) const {
  // Some names repeat in the register map because every controller series has
  // its own block. Without an address the first match wins.
  for (size_t i = 0; i < REGISTER_COUNT; i++) {
    if (strcmp(REGISTERS[i].name, name) == 0)
      return &REGISTERS[i];
  }
  return nullptr;
}

const Register *SolarlifeMppt::find_register(const char *name, uint16_t address) const {
  if (address == REGISTER_ADDRESS_UNSPECIFIED)
    return this->find_register(name);
  for (size_t i = 0; i < REGISTER_COUNT; i++) {
    if (REGISTERS[i].address == address && strcmp(REGISTERS[i].name, name) == 0)
      return &REGISTERS[i];
  }
  return nullptr;
}

void SolarlifeMppt::request_write(const Register *reg, bool on) {
  this->request_write_value(reg, on ? 1.0f : 0.0f);
}

void SolarlifeMppt::request_write_value(const Register *reg, float value) {
  if (reg == nullptr)
    return;
  this->queue_.push_back(PendingWrite{reg, value, false});
}

void SolarlifeMppt::request_write_index(const Register *reg, uint16_t index) {
  if (reg == nullptr)
    return;
  this->queue_.push_back(PendingWrite{reg, static_cast<float>(index), true});
}

void SolarlifeMppt::request_button(const Register *reg) {
  if (reg == nullptr)
    return;
  this->queue_.push_back(PendingWrite{reg, 1.0f, true});
}

void SolarlifeMppt::update() {
  if (this->state_ != State::IDLE)
    return;
  if (this->parent_ == nullptr || !this->parent_->connected())
    return;

  if (this->parameters_due_ || millis() - this->last_parameters_ > this->parameters_interval_) {
    this->start_read_(PARAMETERS_START, PARAMETERS_COUNT);
  } else {
    this->start_read_(DETAILS_START, DETAILS_COUNT);
  }
}

void SolarlifeMppt::loop() {
  if (this->state_ != State::IDLE || this->queue_.empty())
    return;
  if (this->parent_ == nullptr || !this->parent_->connected())
    return;

  PendingWrite write = this->queue_.front();
  this->queue_.pop_front();
  this->send_write_(write);
}

void SolarlifeMppt::start_read_(uint16_t start, uint8_t count) {
  uint8_t fc = (start == DETAILS_START) ? FUNCTION_READ_INPUT : FUNCTION_READ_HOLDING;
  std::array<uint8_t, 8> frame{};
  frame[0] = this->device_id_;
  frame[1] = fc;
  frame[2] = start >> 8;
  frame[3] = start & 0xFF;
  frame[4] = 0;
  frame[5] = count;
  uint16_t crc = crc16(frame.data(), 6);
  frame[6] = crc & 0xFF;
  frame[7] = crc >> 8;

  this->expected_start_ = start;
  this->expected_count_ = count;
  this->expected_fc_ = fc;
  this->resync_reported_ = false;
  ESP_LOGD(TAG, "Read start=0x%04X count=%u fc=0x%02X", start, (unsigned) count, fc);
  this->state_ = State::WAIT_READ;
  this->retries_left_ = this->retries_;
  this->frame_length_ = 0;
  this->send_frame_(frame.data(), frame.size());
}

void SolarlifeMppt::send_write_(const PendingWrite &write) {
  const Register &reg = *write.reg;
  uint8_t fc = reg.write_fc;

  this->in_flight_value_ = RegisterValue{};
  uint32_t raw = 0;
  switch (reg.kind) {
    case RegisterKind::NUMBER:
      if (reg.divisor > 0)
        raw = static_cast<uint32_t>(static_cast<int32_t>(lroundf(write.value * reg.divisor)));
      else
        raw = static_cast<uint32_t>(static_cast<int32_t>(lroundf(write.value)));
      break;
    case RegisterKind::BOOL:
      raw = static_cast<uint32_t>(write.value != 0) << reg.shift;
      break;
    case RegisterKind::ENUM: {
      uint32_t index = write.indexed ? static_cast<uint32_t>(lroundf(write.value))
                                     : static_cast<uint32_t>(write.value != 0 ? 1 : 0);
      raw = index << reg.shift;
      break;
    }
    case RegisterKind::DIGITS:
      raw = static_cast<uint32_t>(write.value);
      break;
    case RegisterKind::PACKED_TIME: {
      long minutes = lroundf(write.value);
      if (minutes < 0)
        minutes = 0;
      raw = (static_cast<uint32_t>(minutes / 60) << 8) | static_cast<uint32_t>(minutes % 60);
      break;
    }
  }

  if (reg.kind == RegisterKind::NUMBER || reg.kind == RegisterKind::PACKED_TIME) {
    this->in_flight_value_.number = write.value;
  } else {
    uint16_t index = (raw >> reg.shift) & reg.mask;
    this->in_flight_value_.flag = index != 0;
    if (reg.labels != nullptr && reg.label_count > 0) {
      uint16_t label = index < reg.label_count ? index : 0;
      this->in_flight_value_.text = reg.labels[label];
    }
  }

  std::array<uint8_t, MAX_FRAME> frame{};
  size_t length = 8;
  if (reg.is_32_bit) {
    // A 32-bit value spans two registers, so use write-multiple like the
    // Python protocol client does for the same case.
    frame[0] = this->device_id_;
    frame[1] = 0x10;
    frame[2] = reg.address >> 8;
    frame[3] = reg.address & 0xFF;
    frame[4] = 0;
    frame[5] = 2;
    frame[6] = 4;
    frame[7] = raw >> 24;
    frame[8] = raw >> 16;
    frame[9] = raw >> 8;
    frame[10] = raw;
    uint16_t crc = crc16(frame.data(), 11);
    frame[11] = crc & 0xFF;
    frame[12] = crc >> 8;
    length = 13;
  } else {
    uint16_t value = static_cast<uint16_t>(raw & 0xFFFF);
    if (fc == FUNCTION_WRITE_STATUS)
      value = value != 0 ? 0xFF00 : 0x0000;
    frame[0] = this->device_id_;
    frame[1] = fc;
    frame[2] = reg.address >> 8;
    frame[3] = reg.address & 0xFF;
    frame[4] = value >> 8;
    frame[5] = value & 0xFF;
    uint16_t crc = crc16(frame.data(), 6);
    frame[6] = crc & 0xFF;
    frame[7] = crc >> 8;
  }

  this->in_flight_ = write;
  this->state_ = State::WAIT_WRITE;
  this->retries_left_ = this->retries_;
  this->frame_length_ = 0;
  this->send_frame_(frame.data(), length);
}

void SolarlifeMppt::send_frame_(const uint8_t *frame, size_t length) {
  if (length > MAX_FRAME) {
    ESP_LOGW(TAG, "Frame too long (%u bytes)", (unsigned) length);
    this->reset_();
    return;
  }
  if (this->write_handle_ == 0) {
    ESP_LOGW(TAG, "Write characteristic not found yet, dropping command");
    this->reset_();
    return;
  }
  memcpy(this->last_frame_.data(), frame, length);
  this->last_frame_length_ = length;

  esp_err_t err = esp_ble_gattc_write_char(this->parent_->get_gattc_if(), this->parent_->get_conn_id(),
                                           this->write_handle_, length, const_cast<uint8_t *>(frame),
                                           this->write_with_response_ ? ESP_GATT_WRITE_TYPE_RSP
                                                                      : ESP_GATT_WRITE_TYPE_NO_RSP,
                                           ESP_GATT_AUTH_REQ_NONE);
  if (err != ESP_OK) {
    ESP_LOGW(TAG, "Write failed: %s", esp_err_to_name(err));
    this->reset_();
    return;
  }
  this->arm_timeout_();
}

void SolarlifeMppt::arm_timeout_() {
  this->set_timeout(TIMEOUT_ID, this->timeout_, [this]() { this->on_timeout_(); });
}

void SolarlifeMppt::on_timeout_() {
  if (this->state_ == State::IDLE)
    return;

  if (this->retries_left_ > 0) {
    this->retries_left_--;
    ESP_LOGD(TAG, "No response, retrying (%u left)", this->retries_left_);
    this->frame_length_ = 0;
    this->send_frame_(this->last_frame_.data(), this->last_frame_length_);
    return;
  }

  ESP_LOGW(TAG, "Giving up on command after %u retries", this->retries_);
  // The controller occasionally stops answering until the link is rebuilt.
  if (++this->failed_transactions_ >= 2) {
    this->failed_transactions_ = 0;
    if (this->parent_ != nullptr) {
      ESP_LOGW(TAG, "Controller stopped answering, reconnecting BLE");
      this->parent_->disconnect();
    }
  }
  if (this->state_ == State::WAIT_WRITE) {
    for (auto *entity : this->entities_) {
      if (entity->get_register() == this->in_flight_.reg)
        entity->on_write_failed();
    }
  } else if (this->expected_start_ == PARAMETERS_START) {
    this->parameters_failures_++;
    if (this->parameters_failures_ >= 3) {
      this->parameters_due_ = false;
      this->parameters_failures_ = 0;
      this->last_parameters_ = millis();
    }
  }
  this->reset_();
}

void SolarlifeMppt::reset_() {
  this->cancel_timeout(TIMEOUT_ID);
  this->state_ = State::IDLE;
  this->frame_length_ = 0;
  this->retries_left_ = 0;
}

void SolarlifeMppt::receive_(const uint8_t *data, size_t length) {
  if (length > MAX_FRAME) {
    ESP_LOGW(TAG, "Notification of %u bytes does not fit a frame", (unsigned) length);
    return;
  }
  if (this->frame_length_ + length > MAX_FRAME) {
    ESP_LOGW(TAG, "Frame overflow, dropping %u buffered bytes", (unsigned) this->frame_length_);
    this->frame_length_ = 0;
  }
  memcpy(this->frame_.data() + this->frame_length_, data, length);
  this->frame_length_ += length;

  while (true) {
    size_t frame_length = 0;
    if (!this->frame_ready_(frame_length))
      return;
    if (this->process_frame_(frame_length))
      return;  // handlers reset the state and the buffer
    this->drop_frame_byte_();
  }
}

void SolarlifeMppt::drop_frame_byte_() {
  if (this->frame_length_ == 0)
    return;
  this->frame_length_--;
  if (this->frame_length_ > 0)
    memmove(this->frame_.data(), this->frame_.data() + 1, this->frame_length_);
}

bool SolarlifeMppt::frame_ready_(size_t &length) {
  while (true) {
    // A late byte or repeated frame shifts the response start, so skip bytes
    // until the expected function code and, once known, the controller id match.
    while (this->frame_length_ > 0 && this->frame_[0] != this->device_id_ &&
           this->device_id_ != DEVICE_ID)
      this->drop_frame_byte_();
    if (this->frame_length_ < 2)
      return false;

    uint8_t function_code = this->frame_[1];
    if (function_code == static_cast<uint8_t>(this->expected_fc_ | 0x80)) {
      length = 5;
      return this->frame_length_ >= length;
    }
    if (function_code != this->expected_fc_) {
      if (!this->resync_reported_) {
        this->resync_reported_ = true;
        ESP_LOGW(TAG, "Dropping response for fc 0x%02X, waiting for fc 0x%02X (buffer: %s)", function_code,
                 this->expected_fc_, this->log_hex_(this->frame_.data(), this->frame_length_).c_str());
      }
      this->drop_frame_byte_();
      continue;
    }

    if (this->state_ == State::WAIT_WRITE) {
      length = 8;
      return this->frame_length_ >= length;
    }

    if (this->frame_length_ < 3)
      return false;
    size_t byte_count = this->frame_[2];
    if (byte_count != static_cast<size_t>(this->expected_count_) * 2) {
      if (!this->resync_reported_) {
        this->resync_reported_ = true;
        ESP_LOGW(TAG, "Dropping response with byte count %u, waiting for %u (buffer: %s)", (unsigned) byte_count,
                 (unsigned) (this->expected_count_ * 2),
                 this->log_hex_(this->frame_.data(), this->frame_length_).c_str());
      }
      this->drop_frame_byte_();
      continue;
    }
    length = 3 + byte_count + 2;
    return this->frame_length_ >= length;
  }
}

bool SolarlifeMppt::process_frame_(size_t length) {
  if (crc16(this->frame_.data(), length) != 0) {
    ESP_LOGW(TAG, "CRC mismatch on %u bytes: %s", (unsigned) length, this->log_hex_(this->frame_.data(), length).c_str());
    return false;
  }
  this->cancel_timeout(TIMEOUT_ID);
  this->failed_transactions_ = 0;
  // Address the controller by its own id from now on instead of broadcasting.
  // The protocol default is 1.
  if (this->frame_[0] != this->device_id_) {
    ESP_LOGI(TAG, "Controller id is 0x%02X", this->frame_[0]);
    this->device_id_ = this->frame_[0];
  }

  if (this->frame_[1] & 0x80) {
    ESP_LOGW(TAG, "Device reported an error (code 0x%02X)", this->frame_[2]);
    this->reset_();
    return true;
  }

  if (this->state_ == State::WAIT_WRITE) {
    this->handle_write_frame_(this->frame_.data());
  } else {
    this->handle_read_frame_(this->frame_.data(), length);
  }
  return true;
}

std::string SolarlifeMppt::log_hex_(const uint8_t *data, size_t length) const {
  char buffer[MAX_FRAME * 3];
  format_hex_pretty_to(buffer, sizeof(buffer), data, length, ' ');
  return buffer;
}

void SolarlifeMppt::handle_read_frame_(const uint8_t *data, size_t length) {
  ESP_LOGD(TAG, "Read frame: start=0x%04X fc=0x%02X byte_count=%u length=%u raw=%s", this->expected_start_, data[1],
           (unsigned) data[2], (unsigned) length, this->log_hex_(data, length).c_str());
  if (data[1] != this->expected_fc_) {
    ESP_LOGW(TAG, "Unexpected function code 0x%02X", data[1]);
    this->reset_();
    return;
  }
  size_t byte_count = data[2];
  if (byte_count != static_cast<size_t>(this->expected_count_) * 2) {
    ESP_LOGW(TAG, "Unexpected byte count %u (expected %u)", (unsigned) byte_count,
             (unsigned) this->expected_count_ * 2);
    this->reset_();
    return;
  }
  if (length < 3 + byte_count + 2) {
    ESP_LOGW(TAG, "Truncated frame");
    this->reset_();
    return;
  }

  const uint8_t *payload = data + 3;
  for (size_t i = 0; i < REGISTER_COUNT; i++) {
    const Register &reg = REGISTERS[i];
    if (reg.address < this->expected_start_ || reg.address >= this->expected_start_ + this->expected_count_)
      continue;
    size_t offset = static_cast<size_t>(reg.address - this->expected_start_) * 2;
    size_t width = reg.is_32_bit ? 4 : 2;
    if (offset + width > byte_count)
      continue;

    uint32_t raw;
    if (reg.is_32_bit) {
      uint16_t lo = encode_uint16(payload[offset], payload[offset + 1]);
      uint16_t hi = encode_uint16(payload[offset + 2], payload[offset + 3]);
      raw = static_cast<uint32_t>(lo) | (static_cast<uint32_t>(hi) << 16);
    } else {
      raw = encode_uint16(payload[offset], payload[offset + 1]);
    }

    this->publish_register_(reg, this->decode_raw_(reg, raw));
  }

  if (this->expected_start_ == PARAMETERS_START) {
    this->parameters_due_ = false;
    this->parameters_failures_ = 0;
    this->last_parameters_ = millis();
  }
  this->reset_();
}

void SolarlifeMppt::handle_write_frame_(const uint8_t *data) {
  uint16_t address = encode_uint16(data[2], data[3]);
  if (address != this->in_flight_.reg->address) {
    ESP_LOGW(TAG, "Write echo for 0x%04X, expected 0x%04X", address, this->in_flight_.reg->address);
    this->reset_();
    return;
  }

  // The Python client publishes the value it requested, not the echo. That
  // also keeps multi-register and status-register writes consistent.
  this->publish_in_flight_();
  this->reset_();
}

void SolarlifeMppt::publish_in_flight_() {
  if (this->in_flight_.reg != nullptr)
    this->publish_register_(*this->in_flight_.reg, this->in_flight_value_);
}

RegisterValue SolarlifeMppt::decode_raw_(const Register &reg, uint32_t raw) const {
  RegisterValue value;
  switch (reg.kind) {
    case RegisterKind::NUMBER: {
      int32_t signed_raw = reg.is_32_bit ? static_cast<int32_t>(raw)
                                         : static_cast<int32_t>(static_cast<int16_t>(raw & 0xFFFF));
      float number = reg.is_signed ? static_cast<float>(signed_raw) : static_cast<float>(raw);
      value.number = reg.divisor > 0 ? number / reg.divisor : number;
      break;
    }
    case RegisterKind::BOOL:
    case RegisterKind::ENUM: {
      uint16_t index = (raw >> reg.shift) & reg.mask;
      value.flag = index != 0;
      if (reg.kind == RegisterKind::ENUM && reg.labels != nullptr && index < reg.label_count)
        value.text = reg.labels[index];
      break;
    }
    case RegisterKind::DIGITS: {
      uint8_t limit = reg.clamp > 0 ? reg.clamp : 9;
      for (int i = reg.digits - 1; i >= 0; i--) {
        uint8_t digit = (raw >> (i * 4)) & 0xF;
        value.text.push_back(static_cast<char>('0' + (digit < limit ? digit : limit)));
      }
      break;
    }
    case RegisterKind::PACKED_TIME: {
      uint16_t hours = (raw >> 8) & 0xFF;
      uint16_t minutes = raw & 0xFF;
      if (minutes > 59)
        minutes = 59;
      value.number = static_cast<float>(hours * 60 + minutes);
      break;
    }
  }
  return value;
}

void SolarlifeMppt::publish_register_(const Register &reg, const RegisterValue &value) {
  for (auto *entity : this->entities_) {
    if (entity->get_register() == &reg)
      entity->on_register_value(value);
  }
}

void SolarlifeMppt::gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gatt_if,
                                        esp_ble_gattc_cb_param_t *param) {
  switch (event) {
    case ESP_GATTC_DISCONNECT_EVT:
      this->reset_();
      this->notify_handle_ = 0;
      this->write_handle_ = 0;
      break;

    case ESP_GATTC_SEARCH_CMPL_EVT: {
      auto *notify = this->parent_->get_characteristic(this->service_uuid_, this->notify_uuid_);
      auto *write = this->parent_->get_characteristic(this->service_uuid_, this->write_uuid_);
      if (notify == nullptr || write == nullptr) {
        ESP_LOGE(TAG,
                 "Characteristics 0x%04X/0x%04X not found in service 0x%04X. If the device uses another "
                 "service, set service_uuid (see the bridge's --list-services output).",
                 this->notify_uuid_, this->write_uuid_, this->service_uuid_);
        break;
      }
      this->notify_handle_ = notify->handle;
      this->write_handle_ = write->handle;
      this->write_with_response_ = (write->properties & ESP_GATT_CHAR_PROP_BIT_WRITE) != 0;
      ESP_LOGI(TAG, "Handles: notify=0x%04X write=0x%04X", this->notify_handle_, this->write_handle_);
      this->parent_->register_for_notify(this->notify_handle_);
      break;
    }

    case ESP_GATTC_REG_FOR_NOTIFY_EVT:
      if (param->reg_for_notify.handle != this->notify_handle_)
        break;
      if (param->reg_for_notify.status != ESP_GATT_OK) {
        ESP_LOGW(TAG, "Notification registration failed: %d", param->reg_for_notify.status);
        break;
      }
      this->node_state = espbt::ClientState::ESTABLISHED;
      this->parameters_due_ = true;
      ESP_LOGI(TAG, "Connected to the MPPT");
      break;

    case ESP_GATTC_NOTIFY_EVT:
      if (param->notify.handle != this->notify_handle_)
        break;
      ESP_LOGV(TAG, "Notify chunk (%u bytes): %s", (unsigned) param->notify.value_len,
               this->log_hex_(param->notify.value, param->notify.value_len).c_str());
      if (this->state_ == State::IDLE)
        break;
      this->receive_(param->notify.value, param->notify.value_len);
      break;

    default:
      break;
  }
}

}  // namespace esphome::solarlife_mppt

#endif  // USE_ESP32
