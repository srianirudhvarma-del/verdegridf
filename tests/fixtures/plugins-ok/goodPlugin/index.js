export default {
  name: 'goodPlugin',
  init(app) {
    this.app = app;
    this.initialized = true;
  },
  async execute(input) {
    return { status: 'ok', echoed: input };
  },
};
