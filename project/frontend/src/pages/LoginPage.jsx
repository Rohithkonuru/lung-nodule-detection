import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input, Alert } from '../components/common/UI';
import { Spinner } from '../components/common/UI';
import AnimatedButton from '../components/AnimatedButton';
import { motion } from 'framer-motion';

export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      const errorMsg = err?.formattedMessage || 
                      err?.message || 
                      'Login failed: Unknown error';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Card */}
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
            <p className="text-gray-300 text-sm mt-1">Clinical Diagnosis System</p>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert
              type="error"
              title="Login Failed"
              message={error}
              className="mb-6"
            />
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <Input
              label="Password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {/* Remember and Forgot */}
            <div className="flex justify-between text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" className="w-4 h-4" />
                <span className="text-gray-300">Remember me</span>
              </label>
              <Link to="/forgot-password" className="text-gray-200 hover:text-white hover:underline">
                Forgot Password?
              </Link>
            </div>

            {/* Submit Button */}
            <AnimatedButton
              type="submit"
              className="w-full mt-8"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner size="sm" />
                  Logging in...
                </span>
              ) : (
                'Login'
              )}
            </AnimatedButton>
          </form>

          {/* Register Link */}
          <p className="text-center text-gray-300 text-sm mt-8">
            Don't have an account?{' '}
            <Link to="/register" className="text-white font-semibold hover:underline">
              Sign up
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
};
