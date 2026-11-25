#include "entities.h"

#ifdef USE_ESP32

#include <cmath>

#include "esphome/core/log.h"

namespace esphome::solarlife_mppt {

namespace {
const char *const TAG = "solarlife_mppt.entity";

const Register *resolve_register(SolarlifeMppt *parent, const std::string &register_name, uint16_t address) {
  if (parent == nullptr) {
    ESP_LOGE(TAG, "Entity has no parent hub");
    return nullptr;
  }
  const Register *reg = parent->find_register(register_name.c_str(), address);
  if (reg == nullptr)
    ESP_LOGE(TAG, "Unknown register '%s' (0x%04X)", register_name.c_str(), address);
  return reg;
}
}  // namespace

void SolarlifeMpptSensor::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptSensor::dump_config() {
  LOG_SENSOR("", "Solarlife MPPT sensor", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptNumber::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptNumber::dump_config() {
  LOG_NUMBER("", "Solarlife MPPT number", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptNumber::control(float value) {
  if (this->register_ == nullptr)
    return;
  ESP_LOGD(TAG, "Writing %s=%f", this->register_name_.c_str(), value);
  this->parent_->request_write_value(this->register_, value);
}

void SolarlifeMpptNumber::on_register_value(const RegisterValue &value) {
  this->last_value_ = value.number;
  this->publish_state(value.number);
}

void SolarlifeMpptNumber::on_write_failed() {
  ESP_LOGW(TAG, "Write to %s failed, reverting", this->register_name_.c_str());
  if (!std::isnan(this->last_value_))
    this->publish_state(this->last_value_);
}

void SolarlifeMpptSelect::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptSelect::dump_config() {
  LOG_SELECT("", "Solarlife MPPT select", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptSelect::control(size_t index) {
  if (this->register_ == nullptr)
    return;
  ESP_LOGD(TAG, "Writing %s=%u", this->register_name_.c_str(), static_cast<unsigned>(index));
  this->parent_->request_write_index(this->register_, index);
}

void SolarlifeMpptSelect::on_register_value(const RegisterValue &value) {
  this->last_value_ = value.text;
  this->publish_state(value.text);
}

void SolarlifeMpptSelect::on_write_failed() {
  ESP_LOGW(TAG, "Write to %s failed, reverting", this->register_name_.c_str());
  if (!this->last_value_.empty())
    this->publish_state(this->last_value_);
}

void SolarlifeMpptBinarySensor::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptBinarySensor::dump_config() {
  LOG_BINARY_SENSOR("", "Solarlife MPPT binary sensor", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptTextSensor::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptTextSensor::dump_config() {
  LOG_TEXT_SENSOR("", "Solarlife MPPT text sensor", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptSwitch::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptSwitch::dump_config() {
  LOG_SWITCH("", "Solarlife MPPT switch", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptSwitch::write_state(bool state) {
  if (this->register_ == nullptr)
    return;
  ESP_LOGD(TAG, "Writing %s=%s", this->register_name_.c_str(), ONOFF(state));
  // Switch registers are write-only, so the controller never reports them.
  // Publish the requested state and let on_write_failed() revert it.
  this->publish_state(state);
  this->parent_->request_write(this->register_, state);
}

void SolarlifeMpptSwitch::on_register_value(const RegisterValue &value) {
  this->last_state_ = value.flag;
  this->publish_state(value.flag);
}

void SolarlifeMpptSwitch::on_write_failed() {
  ESP_LOGW(TAG, "Write to %s failed, reverting", this->register_name_.c_str());
  this->publish_state(this->last_state_);
}

void SolarlifeMpptButton::setup() {
  this->register_ = resolve_register(this->parent_, this->register_name_, this->address_);
  if (this->register_ == nullptr) {
    this->mark_failed();
    return;
  }
  this->parent_->register_entity(this);
}

void SolarlifeMpptButton::dump_config() {
  LOG_BUTTON("", "Solarlife MPPT button", this);
  ESP_LOGCONFIG(TAG, "  Register: %s", this->register_name_.c_str());
}

void SolarlifeMpptButton::press_action() {
  if (this->register_ == nullptr)
    return;
  ESP_LOGD(TAG, "Pressing %s", this->register_name_.c_str());
  this->parent_->request_button(this->register_);
}

}  // namespace esphome::solarlife_mppt

#endif  // USE_ESP32
