import React from 'react';
import { motion } from 'framer-motion';

export default function AnimatedButton({
  children,
  onClick,
  type = 'button',
  disabled = false,
  className = '',
  variant = 'apple',
  as: Component = 'button',
  ...props
}) {
  const base =
    'inline-flex items-center justify-center gap-2 px-5 py-2 rounded-xl font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0f172a] disabled:opacity-60 disabled:cursor-not-allowed';

  const variants = {
    apple:
      'bg-white text-black shadow-md hover:bg-gray-200 hover:scale-105 focus:ring-gray-300',
    gradient:
      'bg-white text-black shadow-md hover:bg-gray-200 hover:scale-105 focus:ring-gray-300',
    ghost:
      'text-gray-100 border border-gray-700 bg-[#111827] hover:bg-gray-800 focus:ring-gray-500',
  };

  const classes = `${base} ${variants[variant] || variants.apple} ${className}`;
  const motionProps = {
    whileHover: disabled ? undefined : { scale: 1.05, y: -1 },
    whileTap: disabled ? undefined : { scale: 0.98 },
    transition: { duration: 0.2, ease: 'easeOut' },
  };

  if (Component === 'button') {
    return (
      <motion.button
        type={type}
        onClick={onClick}
        disabled={disabled}
        className={classes}
        {...motionProps}
        {...props}
      >
        {children}
      </motion.button>
    );
  }

  if (Component === 'span') {
    return (
      <motion.span
        className={classes}
        onClick={onClick}
        role="button"
        tabIndex={0}
        {...motionProps}
        {...props}
      >
        {children}
      </motion.span>
    );
  }

  if (Component === 'div') {
    return (
      <motion.div
        className={classes}
        onClick={onClick}
        role="button"
        tabIndex={0}
        {...motionProps}
        {...props}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <Component className={classes} onClick={onClick} role="button" tabIndex={0} {...props}>
      {children}
    </Component>
  );
}
