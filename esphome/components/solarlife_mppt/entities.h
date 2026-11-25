#pragma once

#ifdef USE_ESP32

#include <string>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/button/button.h"
#include "esphome/components/number/number.h"
#include "esphome/components/select/select.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "solarlife_mppt.h"

namespace esphome::solarlife_mppt {

class SolarlifeMpptSensor : public sensor::Sensor, public Component, public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override { this->publish_state(value.number); }

 protected:
  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
};

class SolarlifeMpptNumber : public number::Number, public Component, public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override;
  void on_write_failed() override;

 protected:
  void control(float value) override;

  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
  float last_value_{NAN};
};

class SolarlifeMpptSelect : public select::Select, public Component, public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override;
  void on_write_failed() override;

 protected:
  void control(size_t index) override;

  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
  std::string last_value_{};
};

class SolarlifeMpptBinarySensor : public binary_sensor::BinarySensor, public Component,
                                 public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override { this->publish_state(value.flag); }

 protected:
  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
};

class SolarlifeMpptTextSensor : public text_sensor::TextSensor, public Component,
                                 public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override { this->publish_state(value.text); }

 protected:
  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
};

class SolarlifeMpptSwitch : public switch_::Switch, public Component, public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &value) override;
  void on_write_failed() override;

 protected:
  void write_state(bool state) override;

  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
  bool last_state_{false};
};

class SolarlifeMpptButton : public button::Button, public Component, public SolarlifeMpptEntity {
 public:
  void setup() override;
  void dump_config() override;
  void set_parent(SolarlifeMppt *parent) { this->parent_ = parent; }
  void set_register(const std::string &register_name) { this->register_name_ = register_name; }
  void set_address(uint16_t address) { this->address_ = address; }
  const Register *get_register() const override { return this->register_; }
  void on_register_value(const RegisterValue &) override {}

 protected:
  void press_action() override;

  SolarlifeMppt *parent_{nullptr};
  std::string register_name_;
  uint16_t address_{REGISTER_ADDRESS_UNSPECIFIED};
  const Register *register_{nullptr};
};

}  // namespace esphome::solarlife_mppt

#endif  // USE_ESP32
