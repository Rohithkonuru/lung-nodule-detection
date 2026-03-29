import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input, Alert } from '../components/common/UI';
import { Spinner } from '../components/common/UI';
import AnimatedButton from '../components/AnimatedButton';
import { motion } from 'framer-motion';

export const RegisterPage = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      await register(formData.email, formData.password, formData.name);
      navigate('/dashboard');
    } catch (err) {
      const errorMsg = err?.formattedMessage || 
                      err?.message || 
                      'Registration failed: Unknown error';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="card rounded-3xl p-8"
        >
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-xl flex items-center justify-center mx-auto mb-4 text-3xl bg-white text-black shadow-sm">
              🫁
            </div>
            <h1 className="text-2xl font-bold text-white">LungAI</h1>
            <p className="text-gray-300 text-sm mt-1">Create Your Account</p>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert
              type="error"
              title="Registration Failed"
              message={error}
              className="mb-6"
            />
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full Name"
              type="text"
              name="name"
              placeholder="Enter your full name"
              value={formData.name}
              onChange={handleChange}
              required
            />

            <Input
              label="Email"
              type="email"
              name="email"
              placeholder="Enter your email"
              value={formData.email}
              onChange={handleChange}
              required
            />

            <Input
              label="Password"
              type="password"
              name="password"
              placeholder="Enter your password (min 6 characters)"
              value={formData.password}
              onChange={handleChange}
              required
            />

            <Input
              label="Confirm Password"
              type="password"
              name="confirmPassword"
              placeholder="Confirm your password"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
            />

            {/* Terms */}
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="w-4 h-4 mt-1" required />
              <span className="text-gray-300">
                I agree to the{' '}
                <Link to="/terms" className="text-gray-200 hover:text-white hover:underline">
                  Terms & Conditions
                </Link>
              </span>
            </label>

            {/* Submit Button */}
            <AnimatedButton
              type="submit"
              className="w-full mt-8"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner size="sm" />
                  Creating Account...
                </span>
              ) : (
                'Sign Up'
              )}
            </AnimatedButton>
          </form>

          {/* Login Link */}
          <p className="text-center text-gray-300 text-sm mt-8">
            Already have an account?{' '}
            <Link to="/login" className="text-white font-semibold hover:underline">
              Login
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
};
